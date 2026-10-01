#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera plantas DXF acotadas y rotuladas desde la especificacion JSON.

Salida en metros, un archivo por nivel. Incluye:
  - muros con su espesor real segun alineacion
  - vanos con codigo (P01, V01...) y cuadro de vanos al costado
  - cotas por cada eje de muro, en dos lineas (parcial y total)
  - rotulo de cada recinto con su superficie declarada
  - simbolo de norte, cota de nivel y vineta con escala

Capas (apagables por separado en AutoCAD / BricsCAD / QCAD):
    A-MURO  A-VANO  A-LOSA  A-ESCA  A-COTA  A-TEXT  A-RECI  A-SIMB  A-CUAD

Uso:
    python tools/scripts/json_to_dxf.py <planta.json> --outdir <dir> \
        [--recintos <recintos.json>]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
except ImportError:
    print("error: falta ezdxf. Instalar con: pip install ezdxf", file=sys.stderr)
    raise SystemExit(2)

CAPAS = [
    ("A-MURO", 7, "muros"),
    ("A-VANO", 4, "puertas y ventanas"),
    ("A-LOSA", 8, "contorno de losa"),
    ("A-ESCA", 3, "escalera"),
    ("A-COTA", 1, "cotas"),
    ("A-TEXT", 2, "textos generales"),
    ("A-RECI", 5, "rotulos de recinto"),
    ("A-SIMB", 6, "simbolos: norte, niveles"),
    ("A-CUAD", 2, "cuadro de vanos"),
]

TOL = 1e-6


def wall_polygon(w):
    """Rectangulo en planta del muro segun su alineacion respecto al eje a-b."""
    (x1, y1), (x2, y2) = w["a"], w["b"]
    t = w["t"]
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < TOL:
        return None
    nx, ny = -dy / L, dx / L

    align = w.get("align", "center")
    if align == "center":
        o1, o2 = -t / 2.0, t / 2.0
    elif align == "left":
        o1, o2 = 0.0, t
    else:
        o1, o2 = -t, 0.0

    return [
        (x1 + nx * o1, y1 + ny * o1),
        (x2 + nx * o1, y2 + ny * o1),
        (x2 + nx * o2, y2 + ny * o2),
        (x1 + nx * o2, y1 + ny * o2),
    ]


def texto(msp, contenido, punto, altura, capa, centrado=False):
    t = msp.add_text(contenido, height=altura, dxfattribs={"layer": capa})
    if centrado:
        t.set_placement(punto, align=TextEntityAlignment.MIDDLE_CENTER)
    else:
        t.set_placement(punto)
    return t


def ejes_de_muro(spec, level_id):
    """Coordenadas X e Y donde hay caras de muro: la base para acotar."""
    xs, ys = set(), set()
    for w in spec["walls"]:
        if w["level"] != level_id:
            continue
        poly = wall_polygon(w)
        if not poly:
            continue
        for x, y in poly:
            xs.add(round(x, 3))
            ys.add(round(y, 3))
    return sorted(xs), sorted(ys)


def filtrar_proximos(vals, minimo=0.70):
    """Descarta cotas demasiado juntas para que la cadena sea legible.

    Con el umbral bajo se generaban parciales de 0,20 y 0,40 m cuyos textos se
    encabalgaban y volvian ilegible toda la linea de cota. 0,70 m deja una
    cadena limpia; el espesor de tabique se lee en el detalle, no aqui.
    El ultimo valor siempre se conserva para que la cadena cierre en el borde.
    """
    if not vals:
        return []
    out = [vals[0]]
    for v in vals[1:]:
        if v - out[-1] >= minimo:
            out.append(v)
    if len(out) > 1 and vals[-1] - out[-1] < minimo:
        out[-1] = vals[-1]
    elif out[-1] != vals[-1]:
        out.append(vals[-1])
    return out


def acotar_eje(msp, valores, base, horizontal, capa="A-COTA"):
    """Cadena de cotas parciales entre valores consecutivos."""
    for a, b in zip(valores, valores[1:]):
        if horizontal:
            dim = msp.add_linear_dim(base=(0, base), p1=(a, base), p2=(b, base),
                                     dxfattribs={"layer": capa})
        else:
            dim = msp.add_linear_dim(base=(base, 0), p1=(base, a), p2=(base, b),
                                     angle=90, dxfattribs={"layer": capa})
        dim.render()


def simbolo_norte(msp, x, y, r=0.9):
    """Flecha de norte.

    Convencion del repositorio: +X este, +Y sur. Por tanto el NORTE apunta
    hacia -Y, es decir hacia ABAJO en el dibujo, y la punta de la flecha y la
    letra N van en esa direccion.
    """
    msp.add_circle((x, y), r, dxfattribs={"layer": "A-SIMB"})
    msp.add_lwpolyline(
        [(x, y - r * 0.95),                      # punta: hacia -Y = norte
         (x - r * 0.28, y + r * 0.5),
         (x, y + r * 0.2),
         (x + r * 0.28, y + r * 0.5)],
        close=True, dxfattribs={"layer": "A-SIMB"})
    texto(msp, "N", (x, y - r - 0.45), 0.30, "A-SIMB", centrado=True)


def simbolo_nivel(msp, x, y, cota):
    """Triangulo de cota de nivel (NPT)."""
    s = 0.22
    msp.add_lwpolyline([(x, y), (x - s, y + s * 1.6), (x + s, y + s * 1.6)],
                       close=True, dxfattribs={"layer": "A-SIMB"})
    texto(msp, "NPT %+.2f" % cota, (x + s * 1.5, y + s * 0.6), 0.22, "A-SIMB")


def cuadro_vanos(msp, vanos, x, y):
    """Tabla de vanos al costado derecho de la planta."""
    if not vanos:
        return
    h = 0.30           # alto de fila
    anchos = [1.2, 2.3, 1.5, 1.5, 1.5]
    encabezados = ["COD", "TIPO", "ANCHO", "ALTO", "ANTEPECHO"]

    texto(msp, "CUADRO DE VANOS", (x, y + h * 1.4), 0.32, "A-CUAD")

    filas = [encabezados] + vanos
    total_ancho = sum(anchos)
    n = len(filas)
    y_sup = y
    y_inf = y - n * h

    # marco exterior y lineas horizontales
    msp.add_lwpolyline([(x, y_sup), (x + total_ancho, y_sup),
                        (x + total_ancho, y_inf), (x, y_inf)],
                       close=True, dxfattribs={"layer": "A-CUAD"})
    for i in range(1, n):
        yy = y_sup - i * h
        msp.add_line((x, yy), (x + total_ancho, yy),
                     dxfattribs={"layer": "A-CUAD"})

    # lineas verticales, una sola vez y de borde a borde
    cx = x
    for a in anchos[:-1]:
        cx += a
        msp.add_line((cx, y_sup), (cx, y_inf), dxfattribs={"layer": "A-CUAD"})

    # textos
    for i, fila in enumerate(filas):
        yy = y_sup - i * h
        cx = x
        for j, celda in enumerate(fila):
            texto(msp, str(celda), (cx + 0.08, yy - h * 0.70), 0.15, "A-CUAD")
            cx += anchos[j]


def vineta(msp, spec, level_id, cota, x, y, ancho=6.0):
    """Vineta con titulo, lamina, escala y notas."""
    alto = 2.6
    msp.add_lwpolyline([(x, y), (x + ancho, y), (x + ancho, y + alto), (x, y + alto)],
                       close=True, dxfattribs={"layer": "A-TEXT"})
    titulo = spec.get("meta", {}).get("titulo", "")
    sub = spec.get("meta", {}).get("subtitulo", "")
    rev = spec.get("meta", {}).get("rev", "")

    texto(msp, titulo[:46], (x + 0.15, y + alto - 0.45), 0.24, "A-TEXT")
    texto(msp, sub[:52], (x + 0.15, y + alto - 0.85), 0.17, "A-TEXT")
    msp.add_line((x, y + alto - 1.05), (x + ancho, y + alto - 1.05),
                 dxfattribs={"layer": "A-TEXT"})
    texto(msp, "PLANTA NIVEL %s   NPT %+.2f m" % (level_id.upper(), cota),
          (x + 0.15, y + alto - 1.45), 0.22, "A-TEXT")
    texto(msp, "Escala 1:50 / 1:100   Medidas en METROS",
          (x + 0.15, y + alto - 1.80), 0.16, "A-TEXT")
    texto(msp, "Rev. %s   Cotas a cara de muro" % rev,
          (x + 0.15, y + alto - 2.10), 0.16, "A-TEXT")
    texto(msp, "VERIFICAR EN OBRA ANTES DE EJECUTAR",
          (x + 0.15, y + alto - 2.40), 0.16, "A-TEXT")


def draw_level(spec, level_id, path, recintos=None):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # metros
    msp = doc.modelspace()
    for nombre, color, descr in CAPAS:
        doc.layers.add(nombre, color=color)

    # estilo de cota legible a escala arquitectonica.
    # dimlfac=1 es imprescindible: el setup por defecto de ezdxf escala x100 y
    # las cotas saldrian en centimetros sobre un dibujo que esta en metros.
    dimstyle = doc.dimstyles.get("EZDXF")
    dimstyle.dxf.dimlfac = 1.0
    dimstyle.dxf.dimtxt = 0.18
    dimstyle.dxf.dimasz = 0.12
    dimstyle.dxf.dimexe = 0.08
    dimstyle.dxf.dimexo = 0.06
    dimstyle.dxf.dimdec = 2
    dimstyle.dxf.dimgap = 0.05

    niveles = {l["id"]: l["z"] for l in spec["levels"]}
    zl = niveles[level_id]
    bx0, by0, bx1, by1 = spec["bbox"]

    # ---- losa
    for s in spec.get("slabs", []):
        if abs(s["z"] - zl) > TOL:
            continue
        for x0, y0, x1, y1 in s["rects"]:
            msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                               close=True, dxfattribs={"layer": "A-LOSA"})

    # ---- muros
    n_muros = 0
    for w in spec["walls"]:
        if w["level"] != level_id:
            continue
        poly = wall_polygon(w)
        if poly:
            msp.add_lwpolyline(poly, close=True, dxfattribs={"layer": "A-MURO"})
            n_muros += 1

    # ---- vanos con codigo
    vanos_tabla = []
    n_p = n_v = 0
    for o in spec.get("openings", []):
        if o["level"] != level_id:
            continue
        x0, y0, x1, y1 = o["rect"]
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                           close=True, dxfattribs={"layer": "A-VANO"})
        ancho = round(max(x1 - x0, y1 - y0), 2)
        sill = o.get("sill", 0.0) or 0.0
        head = o.get("head", 0.0) or 0.0
        alto = round(head - sill, 2)

        if o["kind"] == "door":
            n_p += 1
            cod = "P%02d" % n_p
            tipo = "Puerta"
        elif o["kind"] == "window":
            n_v += 1
            cod = "V%02d" % n_v
            tipo = "Ventana"
        else:
            cod = "A%02d" % (len(vanos_tabla) + 1)
            tipo = "Abertura"

        texto(msp, cod, ((x0 + x1) / 2, (y0 + y1) / 2), 0.14, "A-VANO", centrado=True)
        vanos_tabla.append([cod, tipo, "%.2f" % ancho, "%.2f" % alto,
                            "%.2f" % sill if o["kind"] == "window" else "-"])

    # ---- escalera
    for st in spec.get("stairs", []):
        hu = st["tread"]
        for fl in st["flights"]:
            x0, x1 = fl["x"]
            y = fl["y_start"]
            d = fl["dir"]
            for k in range(fl["steps"]):
                ya = y + d * k * hu
                yb = y + d * (k + 1) * hu
                msp.add_lwpolyline(
                    [(x0, min(ya, yb)), (x1, min(ya, yb)),
                     (x1, max(ya, yb)), (x0, max(ya, yb))],
                    close=True, dxfattribs={"layer": "A-ESCA"})
            if fl.get("landing"):
                lx0, ly0, lx1, ly1 = fl["landing"]
                msp.add_lwpolyline([(lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1)],
                                   close=True, dxfattribs={"layer": "A-ESCA"})
            y_fin = y + d * fl["steps"] * hu
            xm = (x0 + x1) / 2
            msp.add_line((xm, y), (xm, y_fin), dxfattribs={"layer": "A-ESCA"})
            # punta de flecha en el sentido de subida
            s = 0.12 * (1 if d > 0 else -1)
            msp.add_lwpolyline(
                [(xm, y_fin), (xm - 0.10, y_fin - s * 1.6), (xm + 0.10, y_fin - s * 1.6)],
                close=True, dxfattribs={"layer": "A-ESCA"})
        n_alz = sum(f["steps"] for f in st["flights"]) + \
            sum(1 for f in st["flights"] if f.get("landing"))
        texto(msp, "SUBE %d x %.3f" % (n_alz, st["riser"]),
              (st["flights"][0]["x"][0], st["flights"][0]["y_start"] + 0.25),
              0.15, "A-ESCA")

    # ---- rotulos de recinto
    n_rec = 0
    if recintos:
        lv = recintos.get("niveles", {}).get(level_id)
        if lv:
            for r in lv.get("recintos", []):
                px, py = r["punto"]
                texto(msp, r["nombre"].upper(), (px, py + 0.16), 0.20,
                      "A-RECI", centrado=True)
                area = r.get("area_doc_m2")
                if area is not None:
                    marca = "" if r.get("_area_verificada") else " (s/doc)"
                    texto(msp, "%.2f m2%s" % (area, marca), (px, py - 0.18),
                          0.15, "A-RECI", centrado=True)
                n_rec += 1

    # ---- cotas por eje
    xs, ys = ejes_de_muro(spec, level_id)
    xs_f = filtrar_proximos([v for v in xs if bx0 - 0.5 <= v <= bx1 + 0.5])
    ys_f = filtrar_proximos([v for v in ys if by0 - 0.5 <= v <= by1 + 0.5])

    acotar_eje(msp, xs_f, by0 - 1.3, horizontal=True)
    acotar_eje(msp, ys_f, bx0 - 1.3, horizontal=False)
    # cota total
    dim = msp.add_linear_dim(base=(0, by0 - 2.6), p1=(bx0, by0), p2=(bx1, by0),
                             dxfattribs={"layer": "A-COTA"})
    dim.render()
    dim = msp.add_linear_dim(base=(bx0 - 2.6, 0), p1=(bx0, by0), p2=(bx0, by1),
                             angle=90, dxfattribs={"layer": "A-COTA"})
    dim.render()

    # ---- simbolos y textos
    simbolo_norte(msp, bx1 + 2.2, by1 - 1.0)
    simbolo_nivel(msp, bx0 + 0.4, by0 + 0.4, zl)
    cuadro_vanos(msp, vanos_tabla, bx1 + 1.5, by1 - 3.2)
    vineta(msp, spec, level_id, zl, bx0, by1 + 1.2)

    if recintos:
        texto(msp, "(s/doc) = superficie declarada en el documento, no medida",
              (bx0, by0 - 3.4), 0.16, "A-TEXT")

    doc.saveas(path)
    return n_muros, len(vanos_tabla), n_rec


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--recintos")
    args = ap.parse_args(argv)

    spec = json.load(open(args.spec, encoding="utf-8"))
    recintos = None
    if args.recintos and Path(args.recintos).exists():
        recintos = json.load(open(args.recintos, encoding="utf-8"))

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    for lvl in spec["levels"]:
        path = out / ("planta_%s.dxf" % lvl["id"])
        m, v, r = draw_level(spec, lvl["id"], str(path), recintos)
        print("%s  (%d muros, %d vanos, %d recintos rotulados)" % (path, m, v, r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
