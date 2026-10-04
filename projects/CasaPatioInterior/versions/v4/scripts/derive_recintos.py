#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deriva los polígonos de recinto de la vivienda a partir de los documentos base.

Entradas (ninguna se modifica):
  * ../v0/source/casa_rev_h.json      muros, ejes y espesores (v0, se importa)
  * sources/Test/planos_vivienda_rev_G.html   rótulos y superficies declaradas

Salida: v4/calcs/recintos_v4.json  (coordenadas del documento: X este, Y norte, m)

Cómo se construye cada recinto
  1. Polígono BRUTO (a ejes): rectángulo/L escrito en la tabla ROOMS. Los
     recintos cerrados por muros se confirmaron contra shapely.polygonize de los
     ejes; los de planta abierta (espacio libre, galerías, comedor/living) se
     delimitan con las cotas del documento porque ahí no hay muro que los separe.
  2. Verificación OBLIGATORIA, si falla el script se detiene:
       - el rótulo del documento cae dentro del polígono
       - area_bruta == area declarada en el documento (±0,01 m2)
  3. Polígono NETO = bruto − huella de muros. Es el que se modela en FreeCAD.

La columna `delimitacion` dice qué fracción del perímetro bruto coincide con un eje
de muro: "muros" (>=99 %) o "inferida" (lo demás). Un recinto "inferido" tiene un
borde que el modelo físico no materializa.

Uso:  python derive_recintos.py
"""
from __future__ import annotations

import html
import json
import math
import re
import sys
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]                       # raíz del repo
SPEC = HERE.parents[1] / "v0" / "source" / "casa_rev_h.json"
DOC = ROOT / "sources" / "Test" / "planos_vivienda_rev_G.html"
OUT = HERE.parent / "calcs" / "recintos_v4.json"

# Calibración del SVG del documento: x_svg = 100 + 34 X ; y_svg = 579.2 - 34 Y
# (comprobada con los ejes A,B,C,D = 0; 4,4; 9,0; 13,0 y 1..4 = 0; 4,2; 10,2; 14)
SX0, SY0, K = 100.0, 579.2, 34.0

R = box  # rect(x0,y0,x1,y1)
# nombre en el documento (MAYÚSCULAS) -> (etiqueta Spanish del Space, tipo, polígono bruto)
# Las etiquetas "Pasillo ..." existen porque tools/area_calc.py clasifica por nombre
# (docs/architecture.md): "pasillo" activa las reglas de circulación.
ROOMS = {
    "p1": {
        "ESCALERA":          ("Escalera",                   "circulacion", R(0, 0, 2.2, 4.2)),
        "BAÑO 2":            ("Baño 2",                     "wet",         R(2.2, 0, 4.4, 2.1)),
        "VESTÍBULO":         ("Hall Escalera",              "circulacion", R(2.2, 2.1, 4.4, 4.2)),
        "HALL DE ACCESO":    ("Hall de Acceso",             "circulacion", R(4.4, 1.5, 6.8, 4.2)),
        "LOGIA":             ("Logia",                      "servicio",    R(6.8, 0, 9.0, 4.2)),
        "PORCHE":            ("Porche",                     "exterior",    R(4.4, 0, 6.8, 1.5)),
        "ESPACIO LIBRE":     ("Espacio Libre",              "habitable",   R(0, 4.2, 2.9, 10.2)),
        "GALERÍA PONIENTE":  ("Pasillo Galería Poniente",   "circulacion", R(2.9, 4.2, 3.9, 10.2)),
        "GALERÍA SUR":       ("Pasillo Galería Sur",        "circulacion", R(3.9, 4.2, 9.0, 5.4)),
        "GALERÍA N":         ("Pasillo Galería Norte",      "circulacion", R(3.9, 9.0, 7.4, 10.2)),
        "CLÓSET":            ("Clóset",                     "servicio",    R(0, 10.2, 2.6, 11.4)),
        "BAÑO 1":            ("Baño 1",                     "wet",         R(0, 11.4, 2.6, 14.0)),
        "DORMITORIO 1":      ("Dormitorio 1",               "habitable",   R(2.6, 10.2, 7.4, 14.0)),
        "COCINA":            ("Cocina",                     "habitable",   R(9.0, 0, 13.0, 3.9)),
        "COMEDOR":           ("Comedor",                    "habitable",   R(9.0, 3.9, 13.0, 7.6)),
        "LIVING":            ("Living",                     "habitable",   R(9.0, 7.6, 13.0, 14.0)),
        "PATIO INTERIOR":    ("Patio Interior",             "exterior",    R(3.9, 5.4, 9.0, 9.0)),
        "PASO CUBIERTO":     ("Paso Cubierto",              "exterior",    R(7.4, 10.2, 9.0, 14.0)),
    },
    "p2": {
        "ESCALERA":          ("Escalera",                   "circulacion", R(0, 0, 2.2, 4.2)),
        "BAÑO 3":            ("Baño 3",                     "wet",         R(2.2, 0, 4.4, 3.0)),
        "SALA DE ESTAR":     ("Sala de Estar",              "habitable",
                              unary_union([R(0, 4.2, 4.4, 6.6), R(2.2, 3.0, 4.4, 4.2)])),
        "DORMITORIO 4":      ("Dormitorio 4",               "habitable",   R(4.4, 0, 9.0, 4.2)),
        "DORMITORIO 5":      ("Dormitorio 5",               "habitable",   R(0, 6.6, 4.4, 10.2)),
        "PASARELA PONIENTE": ("Pasillo Pasarela Poniente",  "circulacion", R(4.4, 4.2, 5.4, 10.2)),
        "PASARELA SUR":      ("Pasillo Pasarela Sur",       "circulacion", R(5.4, 4.2, 9.0, 5.4)),
        "PASARELA N":        ("Pasillo Pasarela Norte",     "circulacion", R(5.4, 9.0, 7.4, 10.2)),
        "WALK-IN CLÓSET":    ("Walk-in Clóset",             "servicio",    R(0, 10.2, 2.8, 11.6)),
        "BAÑO PRINCIPAL":    ("Baño Principal",             "wet",         R(0, 11.6, 2.8, 14.0)),
        "DORMITORIO PRINCIPAL": ("Dormitorio Principal",    "habitable",   R(2.8, 10.2, 9.0, 14.0)),
    },
}
# Vacíos de losa: el documento los declara "no computables"; no son Space.
VOIDS = {
    "p2": {
        "VACÍO PATIO INTERIOR": ("Vacío Patio Interior", R(5.4, 5.4, 9.0, 9.0)),
        "VACÍO":                ("Vacío Paso Descubierto", R(7.4, 9.0, 9.0, 10.2)),
    },
}
# Recintos exteriores/descubiertos que el documento rotula sin superficie propia
# (aparece como texto "descubierto") y que se agregan al p1 con su geometría.
EXTRA_P1 = {
    "Paso Descubierto": ("exterior", R(7.4, 9.0, 9.0, 10.2), 1.92),
}


def num(s: str) -> float:
    return float(re.match(r"[\d,]+", s).group(0).replace(",", "."))


def doc_labels():
    h = DOC.read_text(encoding="utf-8")
    starts = [m.start() for m in re.finditer("<svg", h)]
    ends = [m.end() for m in re.finditer("</svg>", h)]
    out = {}
    for si, lv in ((0, "p1"), (1, "p2")):
        seg = h[starts[si]:ends[si]]
        texts = [(float(m.group(1)), float(m.group(2)), m.group(3), html.unescape(m.group(4)))
                 for m in re.finditer(
                     r'<text x="([\d.]+)" y="([\d.]+)"[^>]*class="([^"]*)"[^>]*>([^<]*)</text>', seg)]
        lst = {}
        for i, (x, y, c, s) in enumerate(texts):
            if c == "rec" and i + 1 < len(texts) and texts[i + 1][2] == "rec-a" \
                    and "m" in texts[i + 1][3]:
                lst[s.strip()] = ((x - SX0) / K, (SY0 - y) / K, texts[i + 1][3])
        out[lv] = lst
    return out


def wall_footprint(w):
    (ax, ay), (bx, by) = w["a"], w["b"]
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    o0, o1 = (0.0, w["t"]) if w.get("align", "center") == "left" else (-w["t"] / 2, w["t"] / 2)
    pts = [(ax + nx * o0, ay + ny * o0), (bx + nx * o0, by + ny * o0),
           (bx + nx * o1, by + ny * o1), (ax + nx * o1, ay + ny * o1)]
    return Polygon(pts)


def perimeter_on_walls(poly, axes, tol=0.11):
    ring = LineString(list(poly.exterior.coords))
    near = unary_union([a.buffer(tol) for a in axes])
    return ring.intersection(near).length / ring.length


def main() -> int:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    labels = doc_labels()
    result = {
        "_nota": [
            "Generado por derive_recintos.py. Coordenadas del documento: X este, Y norte (m).",
            "area_bruta_m2 = a ejes (lo que declara el documento); area_neta_m2 = menos huella de muros.",
            "delimitacion 'inferida' = parte del perímetro no coincide con un eje de muro.",
        ],
        "niveles": {},
    }
    errors = []

    for lv in ("p1", "p2"):
        walls = [w for w in spec["walls"] if w["level"] == lv]
        foot = unary_union([wall_footprint(w) for w in walls])
        axes = [LineString([w["a"], w["b"]]) for w in walls]
        rooms = []
        for key, (label, tipo, gross) in ROOMS[lv].items():
            if key not in labels[lv]:
                errors.append("%s: rótulo '%s' no está en el documento" % (lv, key))
                continue
            lx, ly, atxt = labels[lv][key]
            decl = num(atxt)
            if not gross.buffer(1e-6).contains(Point(lx, ly)):
                errors.append("%s %s: el rótulo (%.2f, %.2f) cae fuera del polígono" % (lv, key, lx, ly))
            if abs(gross.area - decl) > 0.011:
                errors.append("%s %s: área a ejes %.3f != declarada %.2f" % (lv, key, gross.area, decl))
            net = gross.difference(foot)
            if net.geom_type == "MultiPolygon":
                net = max(net.geoms, key=lambda g: g.area)
            cov = perimeter_on_walls(gross, axes) if gross.geom_type == "Polygon" else None
            rooms.append({
                "nombre_doc": key.title() if False else key,
                "label": label,
                "tipo": tipo,
                "area_doc_m2": decl,
                "area_bruta_m2": round(gross.area, 3),
                "area_neta_m2": round(net.area, 3),
                "perimetro_sobre_muros": round(cov, 3) if cov is not None else None,
                "delimitacion": "muros" if cov is not None and cov >= 0.99 else "inferida",
                "punto_rotulo": [round(lx, 3), round(ly, 3)],
                "bruto": [list(map(lambda v: round(v, 4), p)) for p in gross.exterior.coords][:-1],
                "neto": [list(map(lambda v: round(v, 4), p)) for p in net.exterior.coords][:-1],
            })
        # recintos extra del p1 sin superficie propia en el cuadro
        if lv == "p1":
            for label, (tipo, gross, decl) in EXTRA_P1.items():
                net = gross.difference(foot)
                if net.geom_type == "MultiPolygon":
                    net = max(net.geoms, key=lambda g: g.area)
                rooms.append({
                    "nombre_doc": "(PASO DESCUBIERTO)", "label": label, "tipo": tipo,
                    "area_doc_m2": decl, "area_bruta_m2": round(gross.area, 3),
                    "area_neta_m2": round(net.area, 3),
                    "perimetro_sobre_muros": round(perimeter_on_walls(gross, axes), 3),
                    "delimitacion": "inferida",
                    "punto_rotulo": [round(gross.centroid.x, 3), round(gross.centroid.y, 3)],
                    "bruto": [list(map(lambda v: round(v, 4), p)) for p in gross.exterior.coords][:-1],
                    "neto": [list(map(lambda v: round(v, 4), p)) for p in net.exterior.coords][:-1],
                })
        voids = []
        for key, (label, gross) in VOIDS.get(lv, {}).items():
            decl = num(labels[lv][key][2]) if key in labels[lv] else None
            if decl is not None and abs(gross.area - decl) > 0.011:
                errors.append("%s %s: vacío %.3f != declarado %.2f" % (lv, key, gross.area, decl))
            voids.append({"label": label, "area_doc_m2": decl, "area_bruta_m2": round(gross.area, 3),
                          "bruto": [list(p) for p in gross.exterior.coords][:-1]})
        # recintos del doc que no tienen polígono aquí
        known = set(ROOMS[lv]) | set(VOIDS.get(lv, {}))
        for k in labels[lv]:
            if k not in known:
                errors.append("%s: rótulo del documento sin polígono: %s" % (lv, k))
        result["niveles"][lv] = {"recintos": rooms, "vacios": voids}

    if errors:
        print("FALLA la verificación contra el documento:")
        for e in errors:
            print("  -", e)
        return 1

    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    for lv, nv in result["niveles"].items():
        print(lv)
        for r in nv["recintos"]:
            print("  %-26s doc %6.2f  a ejes %6.2f  neto %6.2f  %-8s %3.0f%% sobre muros"
                  % (r["label"], r["area_doc_m2"], r["area_bruta_m2"], r["area_neta_m2"],
                     r["delimitacion"], 100 * (r["perimetro_sobre_muros"] or 0)))
    print("escrito", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
