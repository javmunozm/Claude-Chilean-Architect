# -*- coding: utf-8 -*-
"""Mide el modelo FCStd v4 y escribe el extract que consume tools/norm_check.py.

    MEASURE_MODEL=<casa_v4.FCStd> MEASURE_OUT=<model_extract.json> V2_DIR=<v2> \
      "E:/FreeCAD/bin/freecadcmd.exe" measure_v4.py

Base: tools/area_calc.extract() (la herramienta compartida, sin modificar). Se le
suma lo que esa herramienta no produce y las reglas necesitan o conviene medir:

  * Space: nivel, superficie bruta/declarada del documento, altura libre máx.
  * Losas: superficie y espesor medidos sobre la forma.
  * Escalera: UNA entidad compuesta (tramo1 + descanso + tramo2 + peldaño de llegada)
    con rise_total, floor_to_floor, rise_deficit, min_width, blondel y holgura de
    cabeza, todo medido sobre las formas, no declarado.

Nada se transcribe del documento salvo la superficie declarada, que va en un campo
aparte (area_doc) justamente para contrastarla con la medida.
"""
import importlib.util
import json
import os
import sys

import FreeCAD

# freecadcmd en una consola que no es UTF-8 se caia al imprimir "Baño" y se tragaba
# la excepcion: el script terminaba sin llegar a sus autocomprobaciones.
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

MM = 1000.0
V2 = os.environ.get("V2_DIR")
MODEL = os.environ.get("MEASURE_MODEL")
OUT = os.environ.get("MEASURE_OUT")
if not (V2 and MODEL and OUT):
    raise SystemExit("faltan V2_DIR / MEASURE_MODEL / MEASURE_OUT en el entorno")
sys.path.insert(0, os.path.join(V2, "scripts"))
import v2lib                                            # noqa: E402

# area_calc.py se carga con otro nombre de módulo: su guardia `__name__ in (...)`
# ejecutaría main() al importarlo como "area_calc".
spec = importlib.util.spec_from_file_location(
    "area_calc_lib", os.path.join(V2, "..", "..", "..", "..", "tools", "area_calc.py"))
area_calc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(area_calc)

REC = json.load(open(os.path.join(V2, "calcs", "recintos_v4.json"), encoding="utf-8"))
doc = FreeCAD.openDocument(MODEL)
doc.recompute()
data = area_calc.extract(doc)


def by_label(prefix):
    return [o for o in doc.Objects if o.Label.startswith(prefix)]


slab = {"p1": by_label("Losa p1")[0], "p2": by_label("Losa p2")[0]}
roofs = [o for o in doc.Objects if getattr(o, "IfcType", "") == "Roof"]
ceil_solids = {"p1": [slab["p2"].Shape] + [r.Shape for r in roofs], "p2": [r.Shape for r in roofs]}
LEVEL_Z = {"p1": 0.0, "p2": slab["p2"].Shape.BoundBox.ZMax}

# ---- Space ----------------------------------------------------------------
rec_index = {}
for lv, nv in REC["niveles"].items():
    for r in nv["recintos"]:
        rec_index[(lv, r["label"])] = r
for ent in data["entities"]:
    if ent["kind"] != "space":
        continue
    obj = doc.getObject(ent["freecad_name"])
    lv = "p2" if abs(obj.Shape.BoundBox.ZMin - LEVEL_Z["p2"]) < 1 else "p1"
    base_label = obj.Label2 or ent["name"]
    r = rec_index[(lv, base_label)]
    ent["tags"] = area_calc.classify(base_label)
    ent["level"] = lv
    ent["area_doc"] = r["area_doc_m2"]
    ent["area_bruta"] = r["area_bruta_m2"]
    ent["delimitacion"] = r["delimitacion"]
    ent["name"] = "%s (%s)" % (base_label, lv)
    if r["tipo"] != "exterior":
        hmin, hmax, n = v2lib.clear_height_range(
            [(x * MM, (y - v2lib.YOFF) * MM) for x, y in r["neto"]], LEVEL_Z[lv], ceil_solids[lv])
        if hmax:
            ent["clear_height_max"] = round(hmax / MM, 3)
            ent["clear_height_min_medida"] = round(hmin / MM, 3)
            ent["clear_height_muestras"] = n
    else:
        ent["_nota_altura"] = "recinto exterior/descubierto: altura referencial 2,60 m, no medida"
        ent.pop("clear_height", None)

# ---- Losas ----------------------------------------------------------------
for ent in data["entities"]:
    if ent["kind"] == "slab":
        obj = doc.getObject(ent["freecad_name"])
        bb = obj.Shape.BoundBox
        top = [f for f in obj.Shape.Faces
               if abs(f.normalAt(0, 0).z) > 0.99 and abs(f.CenterOfMass.z - bb.ZMax) < 1.0]
        ent["area"] = round(sum(f.Area for f in top) / MM ** 2, 3)
        ent["thickness"] = round(bb.ZLength / MM, 3)
        ent["level_z"] = round(bb.ZMax / MM, 3)

# ---- Escalera compuesta ----------------------------------------------------
fl = by_label("Escalera Tramo")
land = by_label("Escalera Descanso")[0]
arr = by_label("Escalera Peldaño de llegada")[0]
stair_ents = [e for e in data["entities"] if e["kind"] == "stair"]
data["entities"] = [e for e in data["entities"] if e["kind"] != "stair"]
riser = float(fl[0].RiserHeight.getValueAs("mm")) / MM
tread = float(fl[0].TreadDepth.getValueAs("mm")) / MM
steps = sum(int(o.NumberOfSteps) for o in fl)
widths = [float(o.Width.getValueAs("mm")) / MM for o in fl]
reached = arr.Shape.BoundBox.ZMax / MM
f2f = (slab["p2"].Shape.BoundBox.ZMax - slab["p1"].Shape.BoundBox.ZMax) / MM
# distancia horizontal, en el sentido de avance (+Y), entre el borde del peldaño de llegada
# y el primer material de la losa del p2 (a 5 cm bajo la cota del peldaño)
import Part
from FreeCAD import Vector as V
abb = arr.Shape.BoundBox
probe = Part.makeLine(V(abb.Center.x, abb.YMax, abb.ZMax - 50.0), V(abb.Center.x, abb.YMax + 8000.0, abb.ZMax - 50.0))
hit = slab["p2"].Shape.common(probe)
gap = (min(e.BoundBox.YMin for e in hit.Edges) - abb.YMax) / MM if hit.Edges else None
# holgura de cabeza: sobre cada punto del recorrido (centro de cada tramo y descanso)
head = []
for o in fl + [land, arr]:
    bb = o.Shape.BoundBox
    zt = bb.ZMax
    for fx in (0.25, 0.5, 0.75):
        for fy in (0.1, 0.5, 0.9):
            x = bb.XMin + fx * bb.XLength
            y = bb.YMin + fy * bb.YLength
            z = v2lib.ceiling_z_at(x, y, zt, [slab["p2"].Shape] + [r.Shape for r in roofs])
            if z is not None:
                head.append((z - zt) / MM)
data["entities"].append({
    "name": "Escalera 1", "freecad_name": ",".join(o.Name for o in fl), "kind": "stair",
    "tags": ["stair"], "steps": steps, "riser": round(riser, 4), "tread": round(tread, 3),
    "min_width": round(min(widths), 3), "rise_total": round(reached, 4),
    "floor_to_floor": round(f2f, 4), "rise_deficit": round(f2f - reached, 4),
    "blondel": round(2 * riser + tread, 4),
    "arrival_gap_to_slab": round(gap, 3) if gap is not None else None,
    "headroom_min": round(min(head), 3) if head else None,
    "headroom_muestras": len(head),
    "_nota": "medido sobre las formas FreeCAD; headroom = hueco libre vertical hasta losa/cubierta "
             "sobre cada tramo (muestreo 3x3 por elemento)",
})

# ---- totales ---------------------------------------------------------------
data["levels"] = {"p1": 0.0, "p2": round(LEVEL_Z["p2"] / MM, 3)}
spc = [e for e in data["entities"] if e["kind"] == "space"]
data["totals"]["space_area_neta_p1"] = round(sum(e["area"] for e in spc if e["level"] == "p1"
                                                 and e.get("clear_height") is not None), 3)
data["totals"]["slab_area"] = round(sum(e["area"] for e in data["entities"] if e["kind"] == "slab"), 3)
data["totals"]["_nota_wall_volume"] = ("suma de volúmenes de los objetos Wall (muros, hastiales y cierres bajo "
                                       "cubierta); los muros se recortan en los encuentros (tools/cubierta.py), "
                                       "así que no hay traslapes contados dos veces")
data["generated_by"] = "area_calc.extract + v4/scripts/measure_v4.py"

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
print("wrote", OUT, "entities:", len(data["entities"]))
