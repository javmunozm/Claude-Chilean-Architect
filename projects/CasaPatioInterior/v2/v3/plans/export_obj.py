# -*- coding: utf-8 -*-
"""Exporta el FCStd a OBJ/MTL CON normales (el OBJ de v0 no las traía: 'vn' = 0).

    EXPORT_MODEL=<casa_v3.FCStd> EXPORT_OBJ=<salida.obj> V2_DIR=<v2> freecadcmd export_obj.py

Metros, eje Y arriba (convención OBJ): (x, y, z)_obj = (X este, Z arriba, -Y norte).
Normales por triángulo (caras planas). Se omiten Space y vanos sin forma.
"""
import os
import sys

import FreeCAD

# freecadcmd en una consola que no es UTF-8 se caia al imprimir "Baño" y se tragaba
# la excepcion: el script terminaba sin llegar a sus autocomprobaciones.
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

MODEL, OBJ, V2 = os.environ["EXPORT_MODEL"], os.environ["EXPORT_OBJ"], os.environ["V2_DIR"]
doc = FreeCAD.openDocument(MODEL)
doc.recompute()
MAT = {"Wall": "muro", "Slab": "losa", "Roof": "cubierta", "Window": "vidrio", "Door": "madera",
       "Stair": "madera", "Stair Flight": "madera", "Furniture": "mueble", "Covering": "pavimento",
       "Building Element Proxy": "terreno"}
groups = {}
for o in doc.Objects:
    t = getattr(o, "IfcType", None)
    if t in MAT and hasattr(o, "Shape") and not o.Shape.isNull():
        groups.setdefault(MAT[t], []).append(o)

lines = ["# casa_v3 — exportado de FreeCAD con normales", "mtllib %s" % os.path.basename(OBJ).replace(".obj", ".mtl")]
nv = nn = ntri = 0
for mat, objs in groups.items():
    lines += ["g " + mat, "usemtl " + mat]
    for o in objs:
        verts, faces = o.Shape.tessellate(0.5)
        P = [(v.x / 1000.0, v.z / 1000.0, -v.y / 1000.0) for v in verts]
        for a, b, c in faces:
            A, B, C = P[a], P[b], P[c]
            u = [B[i] - A[i] for i in range(3)]
            w = [C[i] - A[i] for i in range(3)]
            n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
            l = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
            if l < 1e-12:
                continue
            n = [x / l for x in n]
            for q in (A, B, C):
                lines.append("v %.4f %.4f %.4f" % q)
            lines.append("vn %.4f %.4f %.4f" % tuple(n))
            lines.append("f %d//%d %d//%d %d//%d" % (nv + 1, nn + 1, nv + 2, nn + 1, nv + 3, nn + 1))
            nv += 3
            nn += 1
            ntri += 1
open(OBJ, "w", encoding="utf-8").write("\n".join(lines) + "\n")
mtl = os.path.join(V2, "..", "..", "exports", "casa_rev_h.mtl")
open(OBJ.replace(".obj", ".mtl"), "w", encoding="utf-8").write(open(mtl, encoding="utf-8").read())
print("wrote", OBJ, "triangulos", ntri, "grupos", {k: len(v) for k, v in groups.items()})
