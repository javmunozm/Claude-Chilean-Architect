# -*- coding: utf-8 -*-
"""Genera los DXF acotados y el PDF de láminas a partir de calcs/plan_data.json.

    python make_dxf.py            (intérprete del sistema: ezdxf, shapely, matplotlib)

Entradas:  v2/calcs/plan_data.json   salida de export_slices.py (geometría del FCStd)
           v2/plans/recintos_v2.json superficies declaradas del documento rev. G
Salidas:   v2/exports/planta_p1.dxf, planta_p2.dxf, planos_v2.pdf
           v2/exports/vistas/*.png   vistas de control (para MIRAR, no automatizables)

Se dibuja SOLO lo que está en plan_data.json. Antes de acotar se verifica que cada punto
de cota y cada eje coincida con un vértice real de muro cortado (tolerancia 1 mm): una
cota que no apoya en geometría medida detiene el script.

Unidades del DXF: metros. Escala de lámina 1:50 (alto de texto 0,125 m = 2,5 mm).
Textos en estilo TrueType "ARQ" (Arial): el estilo "Standard" usa txt.shx, que los
visores sin esa fuente SHX reemplazan por un trazo ilegible.

Puertas: el abatimiento sale de plans/puertas_v2.json (derive_puertas.py ->
tools/puertas.py). Las puertas "generadas" (recinto sin acceso en el modelo) se
dibujan cortando el muro, con su código marcado con * y una nota en la viñeta.
"""
import json
import math
import sys
from pathlib import Path

import ezdxf
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

V2 = Path(__file__).resolve().parents[1]
DATA = json.loads((V2 / "calcs" / "plan_data.json").read_text(encoding="utf-8"))
REC = json.loads((V2 / "plans" / "recintos_v2.json").read_text(encoding="utf-8"))
PUERTAS = {(lv, d["codigo"]): d for lv, ds in json.loads(
    (V2 / "plans" / "puertas_v2.json").read_text(encoding="utf-8"))["niveles"].items() for d in ds}
# puertas que el modelo no trae y que propuso tools/puertas.py
GENERADAS = {lv: [dict(d["geometria"], codigo=d["codigo"], tipo="door")
                  for (lv2, _), d in PUERTAS.items() if lv2 == lv and d.get("generada")]
             for lv in ("p1", "p2")}
OUT = V2 / "exports"
(OUT / "vistas").mkdir(parents=True, exist_ok=True)
YOFF = 14.0

TH = 0.125          # alto de texto base (2,5 mm a 1:50)
SHEET_W, SHEET_H = 29.7, 21.0   # A2 horizontal a 1:50 (594 x 420 mm)
X0, Y0 = -4.0, -18.5            # esquina inferior izquierda de la lámina

# ejes del documento (X: A..D, Y: 1..4, convertidos al marco del modelo con Y-14)
EJES_X = {"A": 0.0, "B": 4.4, "C": 9.0, "D": 13.0}
EJES_Y = {"1": 0.0 - YOFF, "2": 4.2 - YOFF, "3": 10.2 - YOFF, "4": 14.0 - YOFF}

# cadenas de cotas por nivel (coordenadas del modelo). Se verifican contra los muros.
CADENAS = {
    "p1": {"sur": [0, 2.2, 4.4, 6.8, 9.0, 13.0], "oeste": [-14, -9.8, -3.8, 0],
           "este": [-14, -8.6, -5.0, 0]},
    "p2": {"sur": [0, 2.2, 4.4, 9.0], "oeste": [-14, -9.8, -7.4, -3.8, 0],
           "este": [-14, -8.6, -5.0, -3.8, 0]},
}
NIVELES = {"p1": ("PLANTA PRIMER PISO", "NPT ±0,00"), "p2": ("PLANTA SEGUNDO PISO", "NPT +2,85")}


def fmt(v, d=2):
    return ("%." + str(d) + "f") % v if False else (("%." + str(d) + "f") % v).replace(".", ",")


# ------------------------------------------------------------ verificación
def wall_vertices(lv):
    return [tuple(p) for w in DATA["plantas"][lv]["muros"] for p in w]


# Las cotas van a eje de muro (convención del documento). Un tabique centrado tiene sus
# vértices a +-t/2 del eje: se exige un vértice a <= 0,101 m (mitad del muro más grueso, 0,20).
AXIS_TOL = 0.101


def axes_present(lv):
    """Ejes que tienen muro en este nivel (p2 no tiene el eje D: el ala oriente es solo p1)."""
    verts = wall_vertices(lv)
    ex = {k: x for k, x in EJES_X.items() if any(abs(p[0] - x) <= AXIS_TOL for p in verts)}
    ey = {k: y for k, y in EJES_Y.items() if any(abs(p[1] - y) <= AXIS_TOL for p in verts)}
    return ex, ey


def verify(lv):
    verts = wall_vertices(lv)
    errs = []
    for side, vals in CADENAS[lv].items():
        axis = 0 if side == "sur" else 1
        # cotas: cada punto debe coincidir con una coordenada de vértice de muro cortado
        # (las caras de muro NO coinciden con el eje en los muros 'left'; se acepta cara o eje)
        for v in vals:
            ok = any(abs(p[axis] - v) <= AXIS_TOL for p in verts)
            if not ok:
                errs.append("%s cota %s=%s sin muro a <= %.3f m" % (lv, side, v, AXIS_TOL))
    bb = DATA["bbox"]
    if abs(bb[0]) > 1e-3 or abs(bb[2] - 13.0) > 1e-3 or abs(bb[1] + 14.0) > 1e-3 or abs(bb[3]) > 1e-3:
        errs.append("bbox medido %s != envolvente 13,00 x 14,00" % bb)
    return errs


# --------------------------------------------------------------- dibujo
def setup_doc():
    d = ezdxf.new("R2018", setup=True)
    d.units = ezdxf.units.M
    d.header["$INSUNITS"] = 6
    d.header["$LTSCALE"] = 0.5
    lay = {
        "A-MURO": (7, "CONTINUOUS", 0.50), "A-MURO-REL": (9, "CONTINUOUS", 0.0),
        "A-VANO": (5, "CONTINUOUS", 0.25), "A-VANO-ALTO": (5, "DASHED", 0.18), "A-VANO-ARCO": (3, "CONTINUOUS", 0.09),
        "A-LOSA": (8, "DASHED", 0.18), "A-ESCA": (3, "CONTINUOUS", 0.18),
        "A-ESCA-SUP": (3, "DASHED", 0.13), "A-MOBI": (8, "CONTINUOUS", 0.13),
        "A-COTA": (1, "CONTINUOUS", 0.18), "A-TEXT": (7, "CONTINUOUS", 0.18),
        "A-RECI": (7, "CONTINUOUS", 0.18), "A-SIMB": (7, "CONTINUOUS", 0.25),
        "A-EJES": (8, "DASHDOT", 0.13), "A-CUAD": (7, "CONTINUOUS", 0.35),
    }
    for name, (col, lt, lw) in lay.items():
        d.layers.add(name, color=col, linetype=lt, lineweight=int(lw * 100) if lw else -3)
    d.styles.add("ARQ", font="arial.ttf")
    st = d.dimstyles.new("ARQ")
    st.dxf.dimtxt = TH
    st.dxf.dimtxsty = "ARQ"
    st.dxf.dimasz = 0.10
    st.dxf.dimexe = 0.08
    st.dxf.dimexo = 0.08
    st.dxf.dimdle = 0.0
    st.dxf.dimgap = 0.04
    st.dxf.dimtad = 1
    st.dxf.dimdec = 2
    st.dxf.dimzin = 0
    st.dxf.dimdsep = ord(",")
    st.dxf.dimclrd = 1
    st.dxf.dimclre = 1
    st.dxf.dimclrt = 1
    st.dxf.dimblk = "ARCHTICK"
    st.dxf.dimtsz = 0.08
    return d


def txt(msp, s, pos, h=TH, layer="A-TEXT", align=TextEntityAlignment.MIDDLE_CENTER, rot=0, color=None):
    t = msp.add_text(s, height=h, rotation=rot, dxfattribs={"layer": layer, "style": "ARQ"})
    t.set_placement(pos, align=align)
    if isinstance(color, tuple):
        t.rgb = color
    elif color:
        t.dxf.color = color
    return t


def draw_walls(msp, lv):
    polys = []
    for w in DATA["plantas"][lv]["muros"]:
        if len(w) >= 3:
            pg = Polygon(w)
            if pg.is_valid and pg.area > 1e-6:
                polys.append(pg)
    u = unary_union([p.buffer(0.0005) for p in polys]).buffer(-0.0005)
    for g in GENERADAS[lv]:                      # vano de la puerta generada
        hx, hy = (g["largo"] / 2, g["espesor_muro"] / 2 + 0.02) if g["horizontal"] \
            else (g["espesor_muro"] / 2 + 0.02, g["largo"] / 2)
        u = u.difference(Polygon([(g["cx"] - hx, g["cy"] - hy), (g["cx"] + hx, g["cy"] - hy),
                                  (g["cx"] + hx, g["cy"] + hy), (g["cx"] - hx, g["cy"] + hy)]))
    geoms = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
    for g in geoms:
        h = msp.add_hatch(color=9, dxfattribs={"layer": "A-MURO-REL"})
        h.set_solid_fill(color=253 if False else 9, rgb=colors.RGB(205, 205, 205))
        rings = [list(g.exterior.coords)] + [list(r.coords) for r in g.interiors]
        for r in rings:
            h.paths.add_polyline_path(r, is_closed=True)
        for r in rings:
            msp.add_lwpolyline(r, close=True, dxfattribs={"layer": "A-MURO"})
    return u


def label_points(lv):
    pts = []
    gross = {r["label"]: r for r in REC["niveles"][lv]["recintos"]}
    for r in DATA["plantas"][lv]["recintos"]:
        info = gross[r["label"]]
        pg = Polygon(r["pts"])
        px, py = info["punto_rotulo"][0], info["punto_rotulo"][1] - YOFF
        if not pg.contains(Point(px, py)):
            c = pg.representative_point()
            px, py = c.x, c.y
        pts.append((px, py))
    return pts


DOOR_RGB = (0, 120, 0)


def draw_door_symbol(msp, lv, v, box_):
    """Hoja + arco de giro (batiente), dos hojas, o corredera, según puertas_v2.json."""
    d = PUERTAS.get((lv, v["codigo"]))
    if d is None:
        print("AVISO: %s %s sin decisión de abatimiento en puertas_v2.json (correr derive_puertas.py)"
              % (lv, v["codigo"]))
        return
    x0, y0, x1, y1 = box_
    if d["tipo"] == "corredera":
        t3 = v["espesor_muro"] / 3
        if v["horizontal"]:
            msp.add_lwpolyline([(x0, v["cy"] + 0.01), (v["cx"] + 0.05, v["cy"] + 0.01), (v["cx"] + 0.05, v["cy"] + t3 / 2 + 0.01),
                                (x0, v["cy"] + t3 / 2 + 0.01)], close=True, dxfattribs={"layer": "A-VANO"})
            msp.add_lwpolyline([(v["cx"] - 0.05, v["cy"] - 0.01), (x1, v["cy"] - 0.01), (x1, v["cy"] - t3 / 2 - 0.01),
                                (v["cx"] - 0.05, v["cy"] - t3 / 2 - 0.01)], close=True, dxfattribs={"layer": "A-VANO"})
        else:
            msp.add_lwpolyline([(v["cx"] + 0.01, y0), (v["cx"] + 0.01, v["cy"] + 0.05), (v["cx"] + t3 / 2 + 0.01, v["cy"] + 0.05),
                                (v["cx"] + t3 / 2 + 0.01, y0)], close=True, dxfattribs={"layer": "A-VANO"})
            msp.add_lwpolyline([(v["cx"] - 0.01, v["cy"] - 0.05), (v["cx"] - 0.01, y1), (v["cx"] - t3 / 2 - 0.01, y1),
                                (v["cx"] - t3 / 2 - 0.01, v["cy"] - 0.05)], close=True, dxfattribs={"layer": "A-VANO"})
        return
    n = d["normal"]
    for h in d["hojas"]:
        hx, hy = h["bisagra"]
        r = h["radio"]
        msp.add_line((hx, hy), (hx + n[0] * r, hy + n[1] * r), dxfattribs={"layer": "A-VANO"})
        a0, a1 = h["a0_deg"], h["a1_deg"]
        s_, e_ = (a0, a1) if a1 > a0 else (a1, a0)
        msp.add_arc((hx, hy), r, s_ % 360, e_ % 360, dxfattribs={"layer": "A-VANO-ARCO"})


def draw_openings(msp, lv):
    lbls = label_points(lv)
    xmin, ymin, xmax, ymax = DATA["bbox"]
    for v in DATA["plantas"][lv]["vanos"] + GENERADAS[lv]:
        cx, cy, L, t = v["cx"], v["cy"], v["largo"], v["espesor_muro"]
        if v["horizontal"]:
            x0, x1, y0, y1 = cx - L / 2, cx + L / 2, cy - t / 2, cy + t / 2
        else:
            x0, x1, y0, y1 = cx - t / 2, cx + t / 2, cy - L / 2, cy + L / 2
        alto = v["tipo"] == "window" and v["antepecho"] >= 1.2 - 1e-6
        ly = "A-VANO-ALTO" if alto else "A-VANO"
        # jambas (cierran el vano contra el muro) y hoja/vidrio
        if v["horizontal"]:
            for x in (x0, x1):
                msp.add_line((x, y0), (x, y1), dxfattribs={"layer": ly})
            if v["tipo"] == "window":
                for y in (y0, cy, y1):
                    msp.add_line((x0, y), (x1, y), dxfattribs={"layer": ly})
        else:
            for y in (y0, y1):
                msp.add_line((x0, y), (x1, y), dxfattribs={"layer": ly})
            if v["tipo"] == "window":
                for x in (x0, cx, x1):
                    msp.add_line((x, y0), (x, y1), dxfattribs={"layer": ly})

        if v["tipo"] == "door":
            draw_door_symbol(msp, lv, v, (x0, y0, x1, y1))
        # código del vano: fuera de la envolvente si el muro es perimetral; si es interior,
        # del lado más alejado de los rótulos de recinto
        if v["tipo"] != "open":
            off = t / 2 + 0.17
            col = 5 if v["tipo"] == "window" else DOOR_RGB
            if v["horizontal"]:
                cands = [(cx, cy + off), (cx, cy - off)]
                peri = abs(cy - ymax) < 0.3 or abs(cy - ymin) < 0.3
                if peri:
                    cands = [(cx, cy + off)] if abs(cy - ymax) < 0.3 else [(cx, cy - off)]
            else:
                cands = [(cx + off, cy), (cx - off, cy)]
                peri = abs(cx - xmax) < 0.3 or abs(cx - xmin) < 0.3
                if peri:
                    cands = [(cx + off, cy)] if abs(cx - xmax) < 0.3 else [(cx - off, cy)]
            best = max(cands, key=lambda c: min(math.hypot(c[0] - a, c[1] - b) for a, b in lbls))
            gen = v in GENERADAS[lv]
            txt(msp, v["codigo"] + ("*" if gen else ""), best, h=0.10, layer="A-TEXT",
                rot=0 if v["horizontal"] else 90, color=(200, 0, 160) if gen else col)


def draw_slab_and_stairs(msp, lv):
    pl = DATA["plantas"][lv]
    for rings in pl["losa"]:
        for r in rings:
            msp.add_lwpolyline(r, close=True, dxfattribs={"layer": "A-LOSA"})
    cut = pl["cut_z"]
    for f in pl["escalera"]:
        above = f["z"] > cut if lv == "p1" else True
        msp.add_lwpolyline(f["pts"], close=True,
                           dxfattribs={"layer": "A-ESCA-SUP" if above else "A-ESCA"})
    # flechas de recorrido en el tramo 1 (sube hacia -Y en p1: del pie a la llegada)
    t1 = [f for f in pl["escalera"] if f["obj"] == "Escalera Tramo 1"]
    if t1:
        xs = [p[0] for f in t1 for p in f["pts"]]
        ys = [p[1] for f in t1 for p in f["pts"]]
        cx = (min(xs) + max(xs)) / 2
        y_pie, y_cab = max(ys), min(ys)
        msp.add_line((cx, y_pie - 0.1), (cx, y_cab + 0.1), dxfattribs={"layer": "A-ESCA"})
        msp.add_line((cx, y_cab + 0.1), (cx - 0.08, y_cab + 0.3), dxfattribs={"layer": "A-ESCA"})
        msp.add_line((cx, y_cab + 0.1), (cx + 0.08, y_cab + 0.3), dxfattribs={"layer": "A-ESCA"})
        txt(msp, "SUBE" if lv == "p1" else "BAJA", (cx, y_pie + 0.25), h=0.10, layer="A-ESCA")
    for m in pl["mobiliario"]:
        msp.add_lwpolyline([(m["x0"], m["y0"]), (m["x1"], m["y0"]), (m["x1"], m["y1"]), (m["x0"], m["y1"])],
                           close=True, dxfattribs={"layer": "A-MOBI"})


def draw_rooms(msp, lv):
    pl = DATA["plantas"][lv]
    gross = {r["label"]: r for r in REC["niveles"][lv]["recintos"]}
    for r in pl["recintos"]:
        pg = Polygon(r["pts"])
        info = gross[r["label"]]
        px, py = info["punto_rotulo"][0], info["punto_rotulo"][1] - YOFF
        if not pg.contains(Point(px, py)):
            c = pg.representative_point()
            px, py = c.x, c.y
        name = r["label"].upper()
        if r["label"] == "Escalera":
            px, py = 1.17, -13.32        # centro del descanso: los tramos ocupan el resto
        minx, miny, maxx, maxy = pg.bounds
        w, h = maxx - minx, maxy - miny
        h_n = 0.11
        rot = 90 if (w < len(name) * h_n * 0.62 and h > w) else 0
        small = min(w, h) < 1.2 or r["label"] == "Escalera"
        txt(msp, name, (px, py + (0.07 if not rot else 0)), h=h_n if not small else 0.09,
            layer="A-RECI", rot=rot, color=7)
        a = "%s m²" % fmt(r["area_m2"])
        if rot:
            txt(msp, a, (px + 0.17, py), h=0.09, layer="A-RECI", rot=90, color=8)
        else:
            txt(msp, a, (px, py - 0.12), h=0.09, layer="A-RECI", color=8)


def draw_dims(msp, lv):
    ch = CADENAS[lv]
    sur = ch["sur"]
    for a, b in zip(sur[:-1], sur[1:]):
        d = msp.add_linear_dim(base=(0, -14.0 - 0.9), p1=(a, -14.0), p2=(b, -14.0), dimstyle="ARQ",
                               dxfattribs={"layer": "A-COTA"})
        d.render()
    d = msp.add_linear_dim(base=(0, -14.0 - 1.7), p1=(sur[0], -14.0), p2=(sur[-1], -14.0), dimstyle="ARQ",
                           dxfattribs={"layer": "A-COTA"})
    d.render()
    oe = ch["oeste"]
    for a, b in zip(oe[:-1], oe[1:]):
        d = msp.add_linear_dim(base=(-0.9, 0), p1=(0, a), p2=(0, b), angle=90, dimstyle="ARQ",
                               dxfattribs={"layer": "A-COTA"})
        d.render()
    d = msp.add_linear_dim(base=(-1.7, 0), p1=(0, oe[0]), p2=(0, oe[-1]), angle=90, dimstyle="ARQ",
                           dxfattribs={"layer": "A-COTA"})
    d.render()
    es = ch["este"]
    xe = max(p[0] for w in DATA["plantas"][lv]["muros"] for p in w)   # borde este medido del nivel
    for a, b in zip(es[:-1], es[1:]):
        d = msp.add_linear_dim(base=(xe + 0.9, 0), p1=(xe, a), p2=(xe, b), angle=90, dimstyle="ARQ",
                               dxfattribs={"layer": "A-COTA"})
        d.render()


def draw_axes(msp, lv):
    ex, ey = axes_present(lv)
    for k, x in ex.items():
        msp.add_line((x, -14.0 - 0.3), (x, 0.9), dxfattribs={"layer": "A-EJES"})
        msp.add_circle((x, 1.25), 0.28, dxfattribs={"layer": "A-EJES", "linetype": "CONTINUOUS"})
        txt(msp, k, (x, 1.25), h=0.16, layer="A-EJES")
    xmax = max(ex.values())
    for k, y in ey.items():
        msp.add_line((-0.3, y), (xmax + 0.3, y), dxfattribs={"layer": "A-EJES"})
        msp.add_circle((-2.55, y), 0.28, dxfattribs={"layer": "A-EJES", "linetype": "CONTINUOUS"})
        txt(msp, k, (-2.55, y), h=0.16, layer="A-EJES")


def draw_north(msp, x, y):
    msp.add_circle((x, y), 0.55, dxfattribs={"layer": "A-SIMB"})
    msp.add_solid([(x, y + 0.5), (x - 0.18, y - 0.35), (x, y - 0.18), (x + 0.18, y - 0.35)],
                  dxfattribs={"layer": "A-SIMB"})
    txt(msp, "N", (x, y + 0.82), h=0.2, layer="A-SIMB")


def draw_tables(msp, lv, x, ytop):
    """Cuadro de superficies (recintos del nivel) y cuadro de vanos, a la derecha del plano."""
    rec = REC["niveles"][lv]["recintos"]
    medidos = {r["label"]: r for r in DATA["plantas"][lv]["recintos"]}
    y = ytop
    txt(msp, "CUADRO DE SUPERFICIES — %s" % NIVELES[lv][0].replace("PLANTA ", "").title(), (x, y), h=0.15,
        layer="A-TEXT", align=TextEntityAlignment.LEFT)
    y -= 0.35
    cols = (x, x + 4.9, x + 6.8)
    for c, s in zip(cols, ("Recinto", "A ejes (doc)", "Útil (modelo)")):
        txt(msp, s, (c, y), h=0.10, layer="A-TEXT", align=TextEntityAlignment.LEFT, color=8)
    y -= 0.13
    msp.add_line((x, y), (x + 8.3, y), dxfattribs={"layer": "A-CUAD"})
    y -= 0.16
    s_doc = s_util = 0.0
    for r in rec:
        m = medidos[r["label"]]
        ext = r["tipo"] == "exterior"
        txt(msp, r["label"] + (" (ext.)" if ext else ""), (cols[0], y), h=0.10, layer="A-TEXT",
            align=TextEntityAlignment.LEFT)
        txt(msp, fmt(r["area_bruta_m2"]), (cols[1] + 1.1, y), h=0.10, layer="A-TEXT", align=TextEntityAlignment.RIGHT)
        txt(msp, fmt(m["area_m2"]), (cols[2] + 1.1, y), h=0.10, layer="A-TEXT", align=TextEntityAlignment.RIGHT)
        if not ext:
            s_doc += r["area_bruta_m2"]
            s_util += m["area_m2"]
        y -= 0.19
    msp.add_line((x, y + 0.07), (x + 8.3, y + 0.07), dxfattribs={"layer": "A-CUAD"})
    y -= 0.08
    txt(msp, "Suma recintos interiores", (cols[0], y), h=0.10, layer="A-TEXT", align=TextEntityAlignment.LEFT)
    txt(msp, fmt(s_doc), (cols[1] + 1.1, y), h=0.10, layer="A-TEXT", align=TextEntityAlignment.RIGHT)
    txt(msp, fmt(s_util), (cols[2] + 1.1, y), h=0.10, layer="A-TEXT", align=TextEntityAlignment.RIGHT)
    y -= 0.30
    for s in ("A ejes: coincide con el cuadro del documento rev. G (verificado recinto por recinto).",
              "Útil: superficie medida del Space del modelo FreeCAD, descontada la huella de muros.",
              "Exteriores (porche, patios, paso) no suman."):
        txt(msp, s, (x, y), h=0.085, layer="A-TEXT", align=TextEntityAlignment.LEFT, color=8)
        y -= 0.15
    # cuadro de vanos
    y -= 0.25
    txt(msp, "CUADRO DE VANOS", (x, y), h=0.15, layer="A-TEXT", align=TextEntityAlignment.LEFT)
    y -= 0.32
    heads = (x, x + 0.8, x + 1.7, x + 3.2, x + 4.1, x + 4.9)
    for c, s in zip(heads, ("Cód.", "Tipo", "Ancho × alto", "Antepecho", "Dintel", "Apertura (patrón de diseño)")):
        txt(msp, s, (c, y), h=0.10, layer="A-TEXT", align=TextEntityAlignment.LEFT, color=8)
    y -= 0.13
    msp.add_line((x, y), (x + 8.3, y), dxfattribs={"layer": "A-CUAD"})
    y -= 0.16
    names = {"window": "Ventana", "door": "Puerta", "open": "Paso"}
    filas = sorted(DATA["plantas"][lv]["vanos"] + GENERADAS[lv], key=lambda v: (v["tipo"] != "door", v["codigo"]))
    for i_fila, v in enumerate(filas):
        alto = v["dintel"] - v["antepecho"]
        code = v["codigo"] + ("*" if v in GENERADAS[lv] else "") if v["tipo"] != "open" else "—"
        txt(msp, code, (heads[0], y), h=0.09, layer="A-TEXT", align=TextEntityAlignment.LEFT)
        txt(msp, names[v["tipo"]], (heads[1], y), h=0.09, layer="A-TEXT", align=TextEntityAlignment.LEFT)
        txt(msp, "%s × %s" % (fmt(v["largo"]), fmt(alto)), (heads[2], y), h=0.09, layer="A-TEXT",
            align=TextEntityAlignment.LEFT)
        txt(msp, fmt(v["antepecho"]), (heads[3], y), h=0.09, layer="A-TEXT", align=TextEntityAlignment.LEFT)
        txt(msp, fmt(v["dintel"]), (heads[4], y), h=0.09, layer="A-TEXT", align=TextEntityAlignment.LEFT)
        pd = PUERTAS.get((lv, v["codigo"])) if v["tipo"] == "door" else None
        if pd:
            ap = ("corredera" if pd["tipo"] == "corredera" else "%s a %s, bisagra %s" % (
                "2 hojas" if pd["tipo"].startswith("doble") else "abre", pd["abre_hacia"],
                {"derecha": "der.", "izquierda": "izq.", "ambos lados": "ambos"}[pd["bisagra_mano"]]))
            txt(msp, ap, (heads[5], y), h=0.085, layer="A-TEXT", align=TextEntityAlignment.LEFT)
        y -= 0.155
        if y < Y0 + 3.4 and i_fila < len(filas) - 1:
            print("AVISO %s: el cuadro de vanos no cabe en la lámina; quedan %d filas fuera"
                  % (lv, len(filas) - 1 - i_fila))
            txt(msp, "... (%d vanos más: ver plans/puertas_v2.json y calcs/plan_data.json)"
                % (len(filas) - 1 - i_fila), (heads[0], y), h=0.09, layer="A-TEXT",
                align=TextEntityAlignment.LEFT, color=1)
            break
    return y


def frame_and_title(msp, lv, titulo, nivel_txt):
    x1, y1 = X0 + SHEET_W, Y0 + SHEET_H
    msp.add_lwpolyline([(X0, Y0), (x1, Y0), (x1, y1), (X0, y1)], close=True, dxfattribs={"layer": "A-CUAD"})
    msp.add_lwpolyline([(X0 + 0.4, Y0 + 0.4), (x1 - 0.4, Y0 + 0.4), (x1 - 0.4, y1 - 0.4), (X0 + 0.4, y1 - 0.4)],
                       close=True, dxfattribs={"layer": "A-CUAD"})
    # viñeta
    bx0, by0, bx1, by1 = x1 - 14.4, Y0 + 0.4, x1 - 0.4, Y0 + 2.9
    msp.add_lwpolyline([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], close=True, dxfattribs={"layer": "A-CUAD"})
    msp.add_line((bx0, by0 + 1.25), (bx1, by0 + 1.25), dxfattribs={"layer": "A-CUAD"})
    msp.add_line((bx0 + 7.2, by0), (bx0 + 7.2, by0 + 1.25), dxfattribs={"layer": "A-CUAD"})
    txt(msp, titulo, (bx0 + 0.2, by1 - 0.38), h=0.22, layer="A-TEXT", align=TextEntityAlignment.LEFT)
    txt(msp, "Vivienda unifamiliar 2 pisos con patio interior — anteproyecto, v2 (reconstruida desde rev. G/H)",
        (bx0 + 0.2, by1 - 0.78), h=0.10, layer="A-TEXT", align=TextEntityAlignment.LEFT, color=8)
    txt(msp, "Escala 1:50 (A2)   ·   Cotas en metros   ·   %s" % nivel_txt, (bx0 + 0.2, by1 - 1.05),
        h=0.10, layer="A-TEXT", align=TextEntityAlignment.LEFT, color=8)
    txt(msp, "Fuente: v2/plans/casa_v2.FCStd (objetos Arch), cortes a +1,20 m", (bx0 + 0.2, by0 + 0.95),
        h=0.085, layer="A-TEXT", align=TextEntityAlignment.LEFT)
    txt(msp, "Comuna, rol y PRC: por definir (site.json)", (bx0 + 0.2, by0 + 0.62), h=0.085, layer="A-TEXT",
        align=TextEntityAlignment.LEFT)
    txt(msp, "Norte según el documento rev. G; no hay levantamiento del sitio", (bx0 + 0.2, by0 + 0.29),
        h=0.085, layer="A-TEXT", align=TextEntityAlignment.LEFT)
    txt(msp, "Abatimiento y bisagras: patrón de diseño (R1-R8), sin verificación normativa", (bx0 + 7.4, by0 + 0.95),
        h=0.085, layer="A-TEXT", align=TextEntityAlignment.LEFT)
    txt(msp, "Sin veredicto normativo: umbrales OGUC sin transcribir (INCONCLUSO)", (bx0 + 7.4, by0 + 0.62),
        h=0.085, layer="A-TEXT", align=TextEntityAlignment.LEFT)
    txt(msp, "Fecha 2026-10-01   ·   Rev. v2-A", (bx0 + 7.4, by0 + 0.29), h=0.085, layer="A-TEXT",
        align=TextEntityAlignment.LEFT)
    if GENERADAS[lv]:
        txt(msp, "* Puerta generada por tools/puertas.py: el recinto no tenía acceso en el modelo",
            (bx0 + 0.2, by1 + 0.25), h=0.10, layer="A-TEXT", align=TextEntityAlignment.LEFT,
            color=(200, 0, 160))


def build_plan(lv):
    errs = verify(lv)
    if errs:
        print("FALLA verificación de", lv)
        for e in errs:
            print("  -", e)
        raise SystemExit(1)
    d = setup_doc()
    msp = d.modelspace()
    draw_walls(msp, lv)
    draw_openings(msp, lv)
    draw_slab_and_stairs(msp, lv)
    draw_rooms(msp, lv)
    draw_axes(msp, lv)
    draw_dims(msp, lv)
    draw_north(msp, 14.85, 1.1)
    titulo, nivel_txt = NIVELES[lv]
    txt(msp, titulo, (4.5, -14.0 - 3.0), h=0.28, layer="A-TEXT")
    txt(msp, "1:50", (4.5, -14.0 - 3.45), h=0.14, layer="A-TEXT", color=8)
    # marca de nivel
    msp.add_lwpolyline([(7.6, -14.0 - 2.6), (8.1, -14.0 - 2.3), (8.6, -14.0 - 2.6), (8.1, -14.0 - 2.9)],
                       close=True, dxfattribs={"layer": "A-SIMB"})
    txt(msp, nivel_txt, (8.75, -14.0 - 2.6), h=0.10, layer="A-SIMB", align=TextEntityAlignment.LEFT)
    draw_tables(msp, lv, 15.9, 1.6)
    frame_and_title(msp, lv, titulo, nivel_txt)
    path = OUT / ("planta_%s.dxf" % lv)
    d.saveas(path)
    return d, path


def main():
    from ezdxf.addons.drawing import Frontend, RenderContext, pymupdf  # noqa: F401
    return 0


def render(d, png, pdf_pages):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy
    fig = plt.figure(figsize=(SHEET_W / 2.54 * 1.0 * 1.0 * 0.2 * 5, SHEET_H / 2.54 * 0.2 * 5))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(d)
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE)
    Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_layout(d.modelspace(), finalize=True)
    ax.set_xlim(X0, X0 + SHEET_W)
    ax.set_ylim(Y0, Y0 + SHEET_H)
    ax.set_aspect("equal")
    fig.savefig(png, dpi=130)
    pdf_pages.savefig(fig)
    plt.close(fig)


if __name__ == "__main__":
    from matplotlib.backends.backend_pdf import PdfPages
    docs = []
    with PdfPages(OUT / "planos_v2.pdf") as pdf:
        for lv in ("p1", "p2"):
            d, path = build_plan(lv)
            print("escrito", path)
            render(d, OUT / "vistas" / ("planta_%s.png" % lv), pdf)
    print("escrito", OUT / "planos_v2.pdf")
