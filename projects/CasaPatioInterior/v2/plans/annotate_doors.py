# -*- coding: utf-8 -*-
"""Registra en cada objeto Door del FCStd su tipo, hacia dónde abre y la mano de bisagra.

    ANNOTATE_MODEL=<casa_v2.FCStd> V2_DIR=<v2> freecadcmd annotate_doors.py

Lee plans/puertas_v2.json (derive_puertas.py). Solo escribe Description; no cambia la forma.
"""
import json
import os

import FreeCAD

V2, MODEL = os.environ["V2_DIR"], os.environ["ANNOTATE_MODEL"]
P = json.load(open(os.path.join(V2, "plans", "puertas_v2.json"), encoding="utf-8"))
doc = FreeCAD.openDocument(MODEL)
n = 0
for lv, ds in P["niveles"].items():
    for d in ds:
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
