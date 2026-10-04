# -*- coding: utf-8 -*-
"""Extrae del modelo FCStd la geometría que dibujan las plantas, cortes y elevaciones.

    EXPORT_MODEL=<casa_v4.FCStd> EXPORT_OUT=<plan_data.json> V2_DIR=<v2> \
      "E:/FreeCAD/bin/freecadcmd.exe" export_slices.py

Todo sale de las formas del modelo (cortes horizontales a +1,20 m sobre cada nivel,
caras superiores de losas y peldaños, huellas de vanos y mobiliario, polígonos de los
Space). make_dxf.py solo dibuja lo que este archivo contiene: ninguna línea del plano
sale del JSON de la rev. H.

Coordenadas: m, marco del modelo (X este, Y norte, origen esquina NO de la envolvente).
"""
import json
import math
import os
import sys

import FreeCAD

# freecadcmd en una consola que no es UTF-8 se caia al imprimir "Baño" y se tragaba
# la excepcion: el script terminaba sin llegar a sus autocomprobaciones.
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass
import Part
from FreeCAD import Vector as V

MM = 1000.0
V2 = os.environ.get("V2_DIR")
MODEL = os.environ.get("EXPORT_MODEL")
OUT = os.environ.get("EXPORT_OUT")
if not (V2 and MODEL and OUT):
    raise SystemExit("faltan V2_DIR / EXPORT_MODEL / EXPORT_OUT")
sys.path.insert(0, os.path.join(V2, "scripts"))

doc = FreeCAD.openDocument(MODEL)
doc.recompute()
CUT = 1.20  # m sobre el nivel


def m(v):
    return round(v / MM, 4)


def pts_of(wire):
    return [[m(v.X), m(v.Y)] for v in wire.OrderedVertexes]


def level_of_label(lbl):
    return "p2" if " p2" in lbl or lbl.endswith("-p2") else "p1"


objs = list(doc.Objects)
slab = {lv: [o for o in objs if o.Label.startswith("Losa " + lv)][0] for lv in ("p1", "p2")}
LEVEL_Z = {"p1": 0.0, "p2": slab["p2"].Shape.BoundBox.ZMax}

data = {"_nota": "generado por export_slices.py desde el FCStd; m; X este, Y norte",
        "levels": {lv: round(z / MM, 4) for lv, z in LEVEL_Z.items()}, "plantas": {}}

for lv in ("p1", "p2"):
    zc = LEVEL_Z[lv] + CUT * MM
    pl = {"cut_z": round(zc / MM, 3), "muros": [], "vanos": [], "losa": [], "escalera": [],
          "mobiliario": [], "recintos": [], "vacios": []}
    # --- muros cortados
    for o in objs:
        if getattr(o, "IfcType", "") == "Wall" and o.Label.startswith("Muro " + lv):
            for w in o.Shape.slice(V(0, 0, 1), zc):
                pl["muros"].append(pts_of(w))
    # --- vanos (huella de la forma, o del perfil si el paso no tiene hoja)
    for o in objs:
        if getattr(o, "IfcType", "") in ("Window", "Door", "Opening Element") and o.Label.endswith("-" + lv):
            shp = o.Shape if not o.Shape.isNull() else o.Base.Shape
            bb = shp.BoundBox
            horiz = bb.XLength >= bb.YLength
            host = o.Hosts[0]
            kind = {"Window": "window", "Door": "door", "Opening Element": "open"}[o.IfcType]
            pl["vanos"].append({
                "codigo": o.Label.rsplit("-", 1)[0], "tipo": kind,
                "cx": m(bb.Center.x), "cy": m(bb.Center.y), "horizontal": bool(horiz),
                "largo": m(bb.XLength if horiz else bb.YLength),
                "espesor_muro": m(float(host.Width.getValueAs("mm"))),
                "antepecho": m(bb.ZMin - LEVEL_Z[lv]), "dintel": m(bb.ZMax - LEVEL_Z[lv]),
                "muro": host.Label,
            })
    # --- losa del nivel (cara superior)
    s = slab[lv]
    zt = s.Shape.BoundBox.ZMax
    for f in s.Shape.Faces:
        if f.normalAt(0, 0).z > 0.99 and abs(f.CenterOfMass.z - zt) < 1.0:
            pl["losa"].append([pts_of(w) for w in f.Wires])
    # --- escalera: caras horizontales superiores, con su cota
    for o in objs:
        if o.Label.startswith("Escalera") and getattr(o, "IfcType", "") in ("Stair", "Stair Flight"):
            for f in o.Shape.Faces:
                if f.normalAt(0, 0).z > 0.99:
                    pl["escalera"].append({"obj": o.Label, "z": m(f.CenterOfMass.z - LEVEL_Z["p1"]),
                                           "pts": pts_of(f.OuterWire)})
    # --- mobiliario del nivel
    for o in objs:
        if getattr(o, "IfcType", "") == "Furniture":
            bb = o.Shape.BoundBox
            lvl_o = "p2" if bb.ZMin >= LEVEL_Z["p2"] - 1 else "p1"
            if lvl_o == lv:
                pl["mobiliario"].append({"obj": o.Label, "x0": m(bb.XMin), "y0": m(bb.YMin),
                                         "x1": m(bb.XMax), "y1": m(bb.YMax)})
    # --- recintos (Space): polígono neto del piso, etiqueta y áreas medidas
    for o in objs:
        if getattr(o, "IfcType", "") == "Space":
            bb = o.Shape.BoundBox
            if (abs(bb.ZMin - LEVEL_Z[lv]) < 1.0):
                floor = [f for f in o.Shape.Faces if f.normalAt(0, 0).z < -0.99 and abs(f.CenterOfMass.z - bb.ZMin) < 1.0][0]
                pl["recintos"].append({
                    "label": o.Label2 or o.Label, "pts": pts_of(floor.OuterWire),
                    "area_m2": round(float(o.Area.getValueAs("mm^2")) / MM ** 2, 3),
                    "altura_m": m(bb.ZLength), "descripcion": o.Description})
    data["plantas"][lv] = pl

# --- bbox de la envolvente, medido sobre los cortes de muro
allpts = [p for lv in data["plantas"].values() for w in lv["muros"] for p in w]
xs, ys = [p[0] for p in allpts], [p[1] for p in allpts]
data["bbox"] = [min(xs), min(ys), max(xs), max(ys)]

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=1, ensure_ascii=False)
print("wrote", OUT, "bbox", data["bbox"],
      {lv: {k: len(v) for k, v in d.items() if isinstance(v, list)} for lv, d in data["plantas"].items()})
