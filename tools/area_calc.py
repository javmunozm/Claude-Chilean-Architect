#!/usr/bin/env python3
"""Area / surface computation from a FreeCAD model.

Runs INSIDE FreeCAD's interpreter, because it needs the Arch object graph:

    AREA_CALC_MODEL=<model.FCStd> AREA_CALC_OUT=<out.json> \
        /e/FreeCAD/bin/freecadcmd.exe tools/area_calc.py

The paths come from the environment, not argv, because freecadcmd treats every
bare argument after the script as a file to IMPORT - passing "out.json" on the
command line makes FreeCAD try to open it as a mesh and abort. (Measured on
FreeCAD 1.1.3; see docs/system.md.) AREA_CALC_OUT is optional: without it the
extract goes to stdout.

Produces the model extract that tools/norm_check.py consumes. Values come from
the solid geometry (Shape.Volume, Face.Area, bounding boxes) - measured off the
model, never transcribed from the designer's intent. Where a quantity cannot be
derived from the shape, the field is omitted rather than guessed, so the checker
reports SKIP instead of inventing a pass.

FreeCAD works internally in millimetres; everything here is converted to metres
(areas to m2, volumes to m3) per the repo unit convention.
"""
from __future__ import annotations

import json
import os
import sys

MM = 1000.0        # mm per metre
MM2 = 1000.0 ** 2  # mm2 per m2
MM3 = 1000.0 ** 3  # mm3 per m3

HABITABLE_HINTS = ("dormitorio", "estar", "comedor", "living", "cocina",
                   "oficina", "sala", "bedroom", "kitchen")
WET_HINTS = ("bano", "baño", "bath", "wc", "aseo")
CIRCULATION_HINTS = ("pasillo", "corridor", "hall", "circulacion", "circulación")


def _label(obj):
    return getattr(obj, "Label", getattr(obj, "Name", "<unnamed>"))


def classify(label):
    """Tag a space by its label so norm rules can select it.

    This is a naming convention, not a measurement: it decides WHICH rules apply,
    while the rules themselves are checked against real geometry. Label your
    Arch Spaces per docs/architecture.md and this stays reliable.
    """
    low = label.lower()
    tags = []
    if any(h in low for h in HABITABLE_HINTS):
        tags.append("habitable")
    if any(h in low for h in WET_HINTS):
        tags.append("wet")
    if any(h in low for h in CIRCULATION_HINTS):
        tags += ["corridor", "circulation"]
    if "dormitorio principal" in low or "master" in low:
        tags.append("dormitorio_principal")
    if "accesible" in low or "accessible" in low:
        tags.append("accessible_bathroom")
    return tags


def space_metrics(obj):
    """Measure an Arch Space: floor area, clear height, minimum plan width."""
    out = {}
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        return out

    bb = shape.BoundBox
    out["clear_height"] = round(bb.ZLength / MM, 3)

    # Minimum horizontal dimension of the bounding box. For a rectangular room
    # this IS the clear width; for an L-shaped room the bbox overstates it, so
    # the value is flagged for the auditor rather than trusted blindly.
    width = min(bb.XLength, bb.YLength) / MM
    out["min_width"] = round(width, 3)
    out["bbox_x"] = round(bb.XLength / MM, 3)
    out["bbox_y"] = round(bb.YLength / MM, 3)

    # Prefer FreeCAD's own computed Area property when the Space exposes one.
    area = getattr(obj, "Area", None)
    if area is not None:
        try:
            out["area"] = round(float(area.getValueAs("mm^2")) / MM2, 3)
        except Exception:
            try:
                out["area"] = round(float(area) / MM2, 3)
            except Exception:
                pass

    if "area" not in out:
        # Fall back to the largest horizontal face (the floor).
        best = 0.0
        for face in shape.Faces:
            try:
                normal = face.normalAt(0, 0)
            except Exception:
                continue
            if abs(normal.z) > 0.9:
                best = max(best, face.Area)
        if best:
            out["area"] = round(best / MM2, 3)

    if "area" in out and out["area"] > 0 and out.get("bbox_x"):
        # Rectangularity: 1.0 means the room fills its bounding box.
        rect = out["area"] / (out["bbox_x"] * out["bbox_y"])
        out["rectangularity"] = round(rect, 3)
        if rect < 0.95:
            out["_warning"] = ("non-rectangular space: min_width is taken from the "
                               "bounding box and may overstate the true clear width - "
                               "have form-auditor measure it")
    return out


def wall_metrics(obj):
    out = {}
    shape = getattr(obj, "Shape", None)
    if shape is not None and not shape.isNull():
        out["volume"] = round(shape.Volume / MM3, 4)
        bb = shape.BoundBox
        out["height"] = round(bb.ZLength / MM, 3)
    for prop, key in (("Length", "length"), ("Width", "thickness")):
        val = getattr(obj, prop, None)
        if val is not None:
            try:
                out[key] = round(float(val.getValueAs("mm")) / MM, 3)
            except Exception:
                pass
    return out


def window_metrics(obj):
    out = {}
    for prop, key in (("Width", "width"), ("Height", "height")):
        val = getattr(obj, prop, None)
        if val is not None:
            try:
                out[key] = round(float(val.getValueAs("mm")) / MM, 3)
            except Exception:
                pass
    if "width" in out and "height" in out:
        out["area"] = round(out["width"] * out["height"], 3)
    return out


def extract(doc):
    entities = []
    totals = {"space_area": 0.0, "window_area": 0.0, "wall_volume": 0.0}

    for obj in doc.Objects:
        ifc_type = getattr(obj, "IfcType", None) or getattr(obj, "IfcRole", None)
        label = _label(obj)
        base = {"name": label, "freecad_name": obj.Name}

        if ifc_type == "Space" or obj.isDerivedFrom("App::FeaturePython") and "Space" in str(ifc_type):
            ent = dict(base, kind="space", tags=classify(label))
            ent.update(space_metrics(obj))
            totals["space_area"] += ent.get("area", 0.0)
            entities.append(ent)

        elif ifc_type in ("Wall", "Wall Standard Case"):
            ent = dict(base, kind="wall", tags=["wall"])
            ent.update(wall_metrics(obj))
            totals["wall_volume"] += ent.get("volume", 0.0)
            entities.append(ent)

        elif ifc_type == "Window":
            ent = dict(base, kind="window", tags=["window"])
            ent.update(window_metrics(obj))
            totals["window_area"] += ent.get("area", 0.0)
            entities.append(ent)

        elif ifc_type == "Door":
            ent = dict(base, kind="door", tags=["door"])
            ent.update(window_metrics(obj))
            # clear_width is NOT the nominal leaf width; it depends on the frame
            # and the opening angle. Deliberately not derived here.
            entities.append(ent)

        elif ifc_type in ("Slab", "Roof", "Plate"):
            ent = dict(base, kind=str(ifc_type).lower(), tags=[str(ifc_type).lower()])
            shape = getattr(obj, "Shape", None)
            if shape is not None and not shape.isNull():
                ent["volume"] = round(shape.Volume / MM3, 4)
            entities.append(ent)

        elif ifc_type == "Stair":
            ent = dict(base, kind="stair", tags=["stair"])
            for prop, key in (("NumberOfSteps", "steps"),):
                val = getattr(obj, prop, None)
                if val is not None:
                    ent[key] = val
            for prop, key in (("TreadDepth", "tread"), ("RiserHeight", "riser")):
                val = getattr(obj, prop, None)
                if val is not None:
                    try:
                        ent[key] = round(float(val.getValueAs("mm")) / MM, 3)
                    except Exception:
                        pass
            entities.append(ent)

    return {
        "project": doc.Name,
        "source_file": doc.FileName,
        "generated_by": "tools/area_calc.py",
        "units": "m, m2, m3",
        "entities": entities,
        "totals": {k: round(v, 3) for k, v in totals.items()},
    }


def main():
    model = os.environ.get("AREA_CALC_MODEL")
    out_path = os.environ.get("AREA_CALC_OUT")

    if not model:
        print("usage: AREA_CALC_MODEL=<model.FCStd> [AREA_CALC_OUT=<out.json>] \\",
              file=sys.stderr)
        print("           freecadcmd tools/area_calc.py", file=sys.stderr)
        print(file=sys.stderr)
        print("Paths go in the environment, not argv: freecadcmd tries to IMPORT",
              file=sys.stderr)
        print("bare arguments as model files.", file=sys.stderr)
        return 2

    if not os.path.exists(model):
        print("error: model not found: %s" % model, file=sys.stderr)
        return 2

    import FreeCAD  # available only inside the FreeCAD interpreter

    doc = FreeCAD.openDocument(model)
    doc.recompute()
    data = extract(doc)

    text = json.dumps(data, indent=2, ensure_ascii=False)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %s  (%d entities, %.2f m2 of space)"
              % (out_path, len(data["entities"]), data["totals"]["space_area"]))
    else:
        print(text)

    if not data["entities"]:
        print("warning: no Arch entities found - is this an Arch/BIM model?",
              file=sys.stderr)
    return 0


# freecadcmd IMPORTS the script rather than executing it as __main__, so a
# plain `if __name__ == "__main__"` guard never fires and the script would load
# and silently do nothing. Accept either entry point. (FreeCAD 1.1.3 - see
# docs/system.md, Known issues.)
if __name__ in ("__main__", "area_calc"):
    _rc = main()
    if _rc:
        sys.exit(_rc)
