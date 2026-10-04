# -*- coding: utf-8 -*-
"""Vistas 2D del FCStd para las láminas: planta de cubierta, 4 elevaciones y 2 cortes.

    V2_DIR=<v5> VIEWS_MODEL=<casa_v5.FCStd> VIEWS_OUT=<views_data.json> \
      "E:/FreeCAD/bin/freecadcmd.exe" export_views.py

Cada vista se obtiene ROTANDO el modelo para que la cámara quede en +Z y proyectando
con TechDraw.projectEx(forma, (0, 0, 1)), que elimina las líneas ocultas. Medido el
2026-10-04: con esa dirección projectEx devuelve (u, v) = (X, Y) sin espejo; con otras
direcciones intercambia o espeja ejes, por eso no se usan.

Marco del modelo (v2 a v5): +X este, +Y norte, +Z arriba, milímetros; el edificio ocupa
X 0…13 000, Y −14 000…0. La salida está en METROS, coordenadas de la vista:
u hacia la derecha del observador, v hacia arriba (cota real en elevaciones y cortes).

Cortes: el modelo se recorta con un semiespacio (se conserva lo que queda delante del
observador) y la sección (Shape.slice en el plano) se entrega aparte como polígonos de
poché. Solo se dibuja lo que está en el modelo: nada se completa a mano.
"""
import json
import os
import sys

import FreeCAD
import Part
import TechDraw
from FreeCAD import Vector as V

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

MM = 1000.0
MODEL, OUT = os.environ["VIEWS_MODEL"], os.environ["VIEWS_OUT"]

# Qué entra en las vistas (IfcType) y qué no: el terreno es una caja de 31 x 33 m que
# taparía todo; mobiliario, recintos y pavimentos no se dibujan en fachada ni corte.
INCLUYE = {"Wall", "Slab", "Roof", "Window", "Door", "Stair", "Stair Flight", "Pipe Segment"}

# Vistas: (nombre, título, derecha, arriba, hacia el observador, corte)
#   corte = None o (normal del plano, posición en mm a lo largo de la normal):
#   se conserva lo que está del lado contrario al observador.
VISTAS = [
    ("cubierta", "PLANTA DE CUBIERTA", V(1, 0, 0), V(0, 1, 0), V(0, 0, 1), None),
    ("elev_sur", "ELEVACIÓN SUR", V(1, 0, 0), V(0, 0, 1), V(0, -1, 0), None),
    ("elev_norte", "ELEVACIÓN NORTE", V(-1, 0, 0), V(0, 0, 1), V(0, 1, 0), None),
    ("elev_oriente", "ELEVACIÓN ORIENTE", V(0, 1, 0), V(0, 0, 1), V(1, 0, 0), None),
    ("elev_poniente", "ELEVACIÓN PONIENTE", V(0, -1, 0), V(0, 0, 1), V(-1, 0, 0), None),
    # A-A: plano X = 1,67 m (tramo 1 de la escalera), mirando al poniente
    ("corte_aa", "CORTE A-A", V(0, 1, 0), V(0, 0, 1), V(1, 0, 0), 1670.0),
    # B-B: plano Y = -4,50 m (patio interior y ambas alas), mirando al norte
    ("corte_bb", "CORTE B-B", V(1, 0, 0), V(0, 0, 1), V(0, -1, 0), -4500.0),
]


def matriz(derecha, arriba, hacia):
    m = FreeCAD.Matrix()
    m.A11, m.A12, m.A13 = derecha.x, derecha.y, derecha.z
    m.A21, m.A22, m.A23 = arriba.x, arriba.y, arriba.z
    m.A31, m.A32, m.A33 = hacia.x, hacia.y, hacia.z
    return m


def segmentos(shape):
    out = []
    for e in shape.Edges:
        pts = e.discretize(Deflection=1.0) if not isinstance(e.Curve, Part.Line) else \
            [e.Vertexes[0].Point, e.Vertexes[-1].Point]
        for a, b in zip(pts[:-1], pts[1:]):
            if (a - b).Length > 0.5:
                out.append([round(a.x / MM, 4), round(a.y / MM, 4), round(b.x / MM, 4), round(b.y / MM, 4)])
    return out


def main():
    doc = FreeCAD.openDocument(MODEL)
    doc.recompute()
    objs = [o for o in doc.Objects if getattr(o, "IfcType", "") in INCLUYE
            and hasattr(o, "Shape") and not o.Shape.isNull() and o.Shape.Solids]
    # una ventana/puerta Arch es hija de un muro: su forma ya está restada del muro y
    # su hoja/vidrio es un sólido propio, así que se incluye como objeto aparte
    solidos = [s for o in objs for s in o.Shape.Solids]
    todo = Part.makeCompound(solidos)
    bb = todo.BoundBox
    print("vistas:", len(objs), "objetos,", len(solidos), "sólidos; bbox m",
          [round(x / MM, 2) for x in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)])
    res = {"_nota": __doc__.split("\n\n")[0], "unidades": "m", "vistas": {}}
    for nombre, titulo, der, arr, hacia, corte in VISTAS:
        forma = todo
        poche = []
        if corte is not None:
            # semiespacio a conservar: del lado opuesto al observador respecto del plano
            n = hacia  # el observador está en +n
            big = 100000.0
            # caja de 'big' a lo largo de la normal, apoyada en el plano, hacia -n
            eje = [abs(n.x), abs(n.y), abs(n.z)].index(1.0)
            signo = 1 if (n.x + n.y + n.z) > 0 else -1
            caja = Part.makeBox(*(big if i == eje else 2 * big for i in range(3)))
            org = [-big, -big, -big]
            org[eje] = corte - big if signo > 0 else corte
            caja.translate(V(*org))
            partes = [s.common(caja) for s in solidos]
            partes = [p for p in partes if p.Volume > 1.0]
            forma = Part.makeCompound(partes)
            normal = V(1, 0, 0) if eje == 0 else (V(0, 1, 0) if eje == 1 else V(0, 0, 1))
            m = matriz(der, arr, hacia)
            for s in solidos:
                for w in s.slice(normal, corte):
                    if not w.isClosed():
                        continue
                    pts = [m.multVec(p) for p in w.discretize(Deflection=1.0)]
                    poche.append([[round(p.x / MM, 4), round(p.y / MM, 4)] for p in pts])
        m = matriz(der, arr, hacia)
        rot = forma.transformGeometry(m)
        r = TechDraw.projectEx(rot, V(0, 0, 1))
        segs = segmentos(r[0]) + segmentos(r[3])
        bbv = rot.BoundBox
        res["vistas"][nombre] = {
            "titulo": titulo, "segmentos": segs, "poche": poche,
            "bbox": [round(bbv.XMin / MM, 3), round(bbv.YMin / MM, 3), round(bbv.XMax / MM, 3), round(bbv.YMax / MM, 3)],
            "corte": None if corte is None else round(corte / MM, 3),
        }
        print("vista", nombre, "segmentos", len(segs), "poché", len(poche),
              "bbox", res["vistas"][nombre]["bbox"])
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    print("wrote", OUT)


if __name__ in ("__main__", "export_views"):
    main()
