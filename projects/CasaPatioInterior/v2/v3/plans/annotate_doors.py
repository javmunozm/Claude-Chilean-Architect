# -*- coding: utf-8 -*-
"""Registra en cada objeto Door del FCStd su tipo, hacia dónde abre y la mano de bisagra.

    ANNOTATE_MODEL=<casa_v3.FCStd> V2_DIR=<v2> freecadcmd annotate_doors.py

Lee plans/puertas_v3.json (derive_puertas.py). Solo escribe Description; no cambia la forma.
"""
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

V2, MODEL = os.environ["V2_DIR"], os.environ["ANNOTATE_MODEL"]
P = json.load(open(os.path.join(V2, "plans", "puertas_v3.json"), encoding="utf-8"))
doc = FreeCAD.openDocument(MODEL)
n = 0
for lv, ds in P["niveles"].items():
    for d in ds:
        if d.get("generada"):           # propuesta de tools/puertas.py: no existe en el modelo
            continue
        objs = [o for o in doc.Objects if o.Label == "%s-%s" % (d["codigo"], lv) and o.IfcType == "Door"]
        if not objs:
            raise SystemExit("puerta sin objeto: %s-%s" % (d["codigo"], lv))
        if d["tipo"] == "corredera":
            txt = "corredera de vidrio | %s" % d["regla"]
        else:
            txt = "%s | abre hacia %s | bisagra %s (empujando) | %s" % (
                d["tipo"], d["abre_hacia"], d["bisagra_mano"], d["regla"])
        objs[0].Description = txt
        n += 1
doc.recompute()
doc.save()
print("annotated", n, "doors")
