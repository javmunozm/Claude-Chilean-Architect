# -*- coding: utf-8 -*-
"""Lámina 6: detalles constructivos, recortados de los cortes del modelo.

    python make_details.py       (intérprete del sistema: ezdxf, shapely)

Entradas:  v5/calcs/views_data.json          cortes A-A y B-B (export_views.py, del FCStd)
           ../v0/source/casa_rev_h.json      niveles, losas, vanos, escalera, cubierta, terreno
           v5/source/terminaciones.json      capas de terminación (propuesta)
           v5/source/estructura.json         sistema estructural (propuesta)
           v5/calcs/aguas_lluvias.json       canales y bajadas
           v5/calcs/estructura_calc.json     viga, losa y cimientos (predimensionamiento)
Salida:    v5/exports/drawings/detalles.dxf  (make_views.py la agrega al PDF)

Las líneas de cada detalle son un recorte del corte del modelo, sin redibujar: lo que
el modelo tiene es lo que se ve. Encima van, en capas aparte y rotuladas como tales,
las terminaciones (estuco, zócalo) y lo que el modelo no tiene (cimiento), sin cotas
inventadas: el cimiento se dibuja como esquema y su tamaño queda al calculista.
"""
import json
from pathlib import Path

from ezdxf.enums import TextEntityAlignment as AL
from shapely.geometry import Polygon, box

import lamina
from make_dxf import setup_doc

VER = Path(__file__).resolve().parents[1]
VISTAS = json.loads((VER / "calcs" / "views_data.json").read_text(encoding="utf-8"))["vistas"]
SPEC = json.loads((VER.parent / "v0" / "source" / "casa_rev_h.json").read_text(encoding="utf-8"))
TERM = {t["id"]: t for t in json.loads((VER / "source" / "terminaciones.json").read_text(encoding="utf-8"))["partidas"]}
EST = json.loads((VER / "source" / "estructura.json").read_text(encoding="utf-8"))
CALC = json.loads((VER / "calcs" / "estructura_calc.json").read_text(encoding="utf-8"))
AGUAS = json.loads((VER / "calcs" / "aguas_lluvias.json").read_text(encoding="utf-8"))
DRAW = VER / "exports" / "drawings"
YOFF = 14.0
ESC = 10                                    # escala de la lámina
K = lambda v: lamina.mm(ESC, v)             # noqa: E731  mm de papel -> m de modelo

NIV = {l["id"]: l["z"] for l in SPEC["levels"]}
Z_TERRENO = SPEC["ground"]["z"]
LOSA_P1 = next(s for s in SPEC["slabs"] if s["z"] == NIV["p1"])
LOSA_P2 = next(s for s in SPEC["slabs"] if s["z"] == NIV["p2"])
TECHO = SPEC["roofs"][0]
ESCALERA = SPEC["stairs"][0]
Y_CORTE_BB = VISTAS["corte_bb"]["corte"] + YOFF        # plano B-B en coordenadas del JSON
VENTANA = next(o for o in SPEC["openings"] if o["kind"] == "window" and o["rect"][0] == 0
               and o["rect"][1] <= Y_CORTE_BB <= o["rect"][3])


def f2(v, n=2):
    return ("%.*f" % (n, v)).replace(".", ",")


# ------------------------------------------------------------------ recorte

def recortar_seg(a, b, c, d, r):
    """Liang-Barsky: segmento (a,b)-(c,d) dentro del rectángulo r = (u0, v0, u1, v1)."""
    u0, v0, u1, v1 = r
    dx, dy = c - a, d - b
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a - u0), (dx, u1 - a), (-dy, b - v0), (dy, v1 - b)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return (a + t0 * dx, b + t0 * dy, a + t1 * dx, b + t1 * dy)


def detalle(msp, vista, r, origen, factor=1.0):
    """Recorte r de la vista, llevado a 'origen' (esquina inferior izquierda) y escalado."""
    u0, v0 = r[0], r[1]
    T = lambda u, v: (origen[0] + (u - u0) * factor, origen[1] + (v - v0) * factor)  # noqa: E731
    caja = box(*r)
    for p in VISTAS[vista]["poche"]:
        g = Polygon(p).buffer(0).intersection(caja)
        for parte in getattr(g, "geoms", [g]):
            if parte.is_empty or parte.area < 1e-6 or parte.geom_type != "Polygon":
                continue
            h = msp.add_hatch(color=252, dxfattribs={"layer": "A-SECC"})
            h.paths.add_polyline_path([T(*xy) for xy in parte.exterior.coords], is_closed=True)
    for a, b, c, d in VISTAS[vista]["segmentos"]:
        s = recortar_seg(a, b, c, d, r)
        if s and abs(s[0] - s[2]) + abs(s[1] - s[3]) > 1e-4:
            msp.add_line(T(s[0], s[1]), T(s[2], s[3]), dxfattribs={"layer": "A-VIST"})
    w, h = (r[2] - r[0]) * factor, (r[3] - r[1]) * factor
    msp.add_lwpolyline([origen, (origen[0] + w, origen[1]), (origen[0] + w, origen[1] + h), (origen[0], origen[1] + h)],
                       close=True, dxfattribs={"layer": "A-DET-MARCO"})
    return T


def titulo(msp, n, s, esc_det, fuente, pos):
    x, y = pos
    msp.add_circle((x + K(5), y + K(4)), K(5), dxfattribs={"layer": "A-TEXT"})
    lamina.txt(msp, "D%d" % n, (x + K(5), y + K(4)), K(3.2), align=AL.MIDDLE_CENTER)
    lamina.txt(msp, s, (x + K(13), y + K(5)), K(3.4))
    lamina.txt(msp, "Escala 1:%d — %s" % (esc_det, fuente), (x + K(13), y + K(0.5)), K(2.0), color=8)


def nota(msp, s, punto, texto_pos, layer="A-DET-NOTA", izq=None):
    """Llamada: línea desde el punto hasta el texto (a la izquierda o derecha del extremo)."""
    msp.add_line(punto, texto_pos, dxfattribs={"layer": layer})
    msp.add_circle(punto, K(0.6), dxfattribs={"layer": layer})
    if izq is None:
        izq = texto_pos[0] < punto[0]
    for i, linea in enumerate(s.split("\n")):
        lamina.txt(msp, linea, (texto_pos[0] + (-K(1) if izq else K(1)), texto_pos[1] - i * K(3.0)), K(2.0),
                   align=AL.MIDDLE_RIGHT if izq else AL.MIDDLE_LEFT)


def cota(msp, p, q, desplaz, texto):
    """Cota alineada entre p y q, corrida 'desplaz' (m de lámina) en perpendicular."""
    import math
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    a = (p[0] + nx * desplaz, p[1] + ny * desplaz)
    b = (q[0] + nx * desplaz, q[1] + ny * desplaz)
    lay = {"layer": "A-COTA"}
    msp.add_line(p, (a[0] + nx * K(1.5), a[1] + ny * K(1.5)), dxfattribs=lay)
    msp.add_line(q, (b[0] + nx * K(1.5), b[1] + ny * K(1.5)), dxfattribs=lay)
    msp.add_line(a, b, dxfattribs=lay)
    for c in (a, b):   # trazo oblicuo de cota arquitectónica
        msp.add_line((c[0] - K(1), c[1] - K(1)), (c[0] + K(1), c[1] + K(1)), dxfattribs=lay)
    ang = math.degrees(math.atan2(dy, dx))
    if ang > 90.01 or ang < -89.99:
        ang -= 180 if ang > 0 else -180
    m = ((a[0] + b[0]) / 2 + nx * K(1.2), (a[1] + b[1]) / 2 + ny * K(1.2))
    lamina.txt(msp, texto, m, K(2.0), layer="A-COTA", align=AL.BOTTOM_CENTER, rot=ang)


def capa(msp, pts, color, layer="A-DET-TERM"):
    h = msp.add_hatch(color=color, dxfattribs={"layer": layer})
    h.paths.add_polyline_path(pts, is_closed=True)
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer, "color": color})


# ------------------------------------------------------------------ detalles

def pendiente():
    return (TECHO["ridge_z"] - TECHO["eave_z"]) / (TECHO["ridge_x"] - TECHO["x_ref"][0])


def bajada_en_vista():
    """La bajada del muro poniente más cercana al plano B-B, del lado que se ve (y > plano)."""
    cand = [(b["muro_xy"][1] - Y_CORTE_BB, i) for i, b in enumerate(AGUAS["bajadas"])
            if abs(b["muro_xy"][0]) < 0.3 and b["muro_xy"][1] > Y_CORTE_BB]
    return min(cand)[1] + 1 if cand else None


def d1_alero(msp, o):
    r = (-0.80, 4.80, 0.60, 5.90)
    T = detalle(msp, "corte_bb", r, o)
    e = TERM[1]["espesor_mm"] / 1000
    # cara inferior de la cubierta en la cara exterior del muro
    z_bajo_alero = TECHO["eave_z"] - TECHO["t"] + (0 - TECHO["x_ref"][0]) * pendiente()
    capa(msp, [T(-e, r[1]), T(0, r[1]), T(0, z_bajo_alero), T(-e, z_bajo_alero)], 2)
    s = pendiente()
    c = AGUAS["canales"][0]
    nb = bajada_en_vista()
    nota(msp, "Cubierta: %s\n(partida 3, propuesta). Espesor modelado %s m" % (TERM[3]["terminacion"].split(" sobre")[0], f2(TECHO["t"])),
         T(0.30, 5.35 + 0.30 * s + 0.6 * TECHO["t"]), T(0.15, 5.86))
    nota(msp, "Canal C1 %s x %s m,\n%s\n(partida 5). Largo %s m" % (
        f2(AGUAS["parametros"]["canal_ancho_m"]["value"]), f2(AGUAS["parametros"]["canal_alto_m"]["value"]),
        TERM[5]["terminacion"].split(",")[0].lower(), f2(c["largo"])),
         T(-0.475, 5.33), T(-0.75, 5.70))
    if nb:
        nota(msp, "Bajada B%d %s x %s m, en vista\n(detrás del plano de corte)" % (nb, f2(AGUAS["parametros"]["bajada_lado_m"]["value"]), f2(AGUAS["parametros"]["bajada_lado_m"]["value"])),
             T(-0.06, 4.90), T(-0.55, 4.95))
    nota(msp, "Tapacán y forro de alero: fibrocemento\npintado (partida 4)", T(-0.40, 5.20), T(-0.75, 5.10))
    nota(msp, "Estuco %d mm + pintura elastomérica\n(partida 1)" % TERM[1]["espesor_mm"], T(-e / 2, 5.00), T(0.25, 5.05))
    nota(msp, "Muro de albañilería confinada %s m\n(estructura.json, propuesta)" % f2(EST["muros_estructurales_espesor_min_m"]),
         T(0.10, 4.88), T(0.25, 4.88))
    cota(msp, T(TECHO["x_ref"][0], 4.86), T(0, 4.86), -K(1), "alero %s" % f2(-TECHO["x_ref"][0]))
    lamina.txt(msp, "pend. %s %% (%s°)" % (f2(100 * s, 1), f2(__import__("math").degrees(__import__("math").atan(s)), 1)),
               T(0.05, 5.62), K(2.0), rot=__import__("math").degrees(__import__("math").atan(s)))
    return T


def d2_losa(msp, o):
    r = (-0.40, 2.25, 0.80, 3.25)
    T = detalle(msp, "corte_bb", r, o)
    e = TERM[1]["espesor_mm"] / 1000
    capa(msp, [T(-e, r[1]), T(0, r[1]), T(0, r[3]), T(-e, r[3])], 2)
    z, t = LOSA_P2["z"], LOSA_P2["t"]
    cota(msp, T(0.70, z - t), T(0.70, z), -K(3), "losa %s" % f2(t))
    cota(msp, T(0, 2.30), T(0.20, 2.30), -K(1), f2(0.20))
    nivel(msp, T(0.80, z), "NPT 2º piso +%s" % f2(z))
    nota(msp, "Losa de HA %s m (estructura.json,\npropuesta; modelo t = %s)" % (f2(EST["losa_p2"]["espesor_m"]), f2(t)),
         T(0.55, z - t / 2), T(0.30, 2.50), izq=False)
    nota(msp, "Cadena de HA en el encuentro muro-losa:\nsección y armadura por el calculista", T(0.10, z - 0.05), T(-0.35, 3.15))
    nota(msp, "Estuco %d mm (partida 1)" % TERM[1]["espesor_mm"], T(-e / 2, 2.45), T(-0.35, 2.45))
    return T


def nivel(msp, p, s):
    x, y = p
    msp.add_lwpolyline([(x, y), (x + K(1.6), y + K(2.4)), (x - K(1.6), y + K(2.4))], close=True,
                       dxfattribs={"layer": "A-NIVEL"})
    lamina.txt(msp, s, (x + K(2.5), y + K(0.6)), K(2.0), layer="A-NIVEL")


def d3_zocalo(msp, o):
    r = (-0.60, -0.85, 0.80, 0.85)
    T = detalle(msp, "corte_bb", r, o)
    e = TERM[2]["espesor_mm"] / 1000
    zz = TERM[2]["altura_m"]
    capa(msp, [T(-e, Z_TERRENO), T(0, Z_TERRENO), T(0, zz), T(-e, zz)], 8)
    capa(msp, [T(-TERM[1]["espesor_mm"] / 1000, zz), T(0, zz), T(0, r[3]), T(-TERM[1]["espesor_mm"] / 1000, r[3])], 2)
    # cimiento: esquema sin medidas (no está en el modelo)
    w = EST["muros_estructurales_espesor_min_m"]
    lay = {"layer": "A-DET-ESQ"}
    zb = -LOSA_P1["t"]
    zc = r[1] + 0.30                       # cara superior del cimiento (esquema)
    msp.add_line(T(0, zb), T(0, zc), dxfattribs=lay)
    msp.add_line(T(w, zb), T(w, zc), dxfattribs=lay)
    msp.add_lwpolyline([T(-0.15, r[1] + 0.05), T(-0.15, zc), T(w + 0.15, zc), T(w + 0.15, r[1] + 0.05)],
                       close=True, dxfattribs=lay)
    sc = CALC["cimientos"]
    nota(msp, "Sobrecimiento y cimiento corrido: ESQUEMA.\n"
              "Ancho y profundidad por el calculista\n"
              "según estudio de suelos (memoria §8:\n"
              "%s–%s m de cálculo; rige el mínimo constructivo)"
              % (f2(min(e_["b_max_m"] for e_ in sc["escenarios"])), f2(max(e_["b_max_m"] for e_ in sc["escenarios"]))),
         T(w + 0.15, r[1] + 0.20), T(0.40, -0.45))
    nota(msp, "Zócalo hasta +%s:\n%s\n(partida 2), color %s" % (f2(zz), TERM[2]["terminacion"].split(",")[0].lower(), TERM[2]["color"]),
         T(-e / 2, 0.30), T(-0.55, 0.45))
    nota(msp, "Losa / radier del 1er piso,\nmodelo t = %s m" % f2(LOSA_P1["t"]), T(0.50, -LOSA_P1["t"] / 2), T(0.28, 0.45), izq=False)
    pav = SPEC["paving"][0]["z"]
    nota(msp, "Terreno %s; pavimento exterior %s\n(partida 8)" % (f2(Z_TERRENO), f2(pav)), T(-0.40, Z_TERRENO), T(-0.55, -0.45))
    nivel(msp, T(0.65, NIV["p1"]), "NPT ±0,00")
    cota(msp, T(-0.02, Z_TERRENO), T(-0.02, zz), K(10), "zócalo %s (terreno a +%s)" % (f2(zz - Z_TERRENO), f2(zz)))
    return T


def d4_escalera(msp, o):
    fl = ESCALERA["flights"][0]
    y0 = fl["y_start"] - YOFF                        # pie del tramo en Y del modelo
    r = (y0 - 1.10, -0.15, y0 + 0.05, 1.00)
    T = detalle(msp, "corte_aa", r, o)
    h, b = ESCALERA["riser"], ESCALERA["tread"]
    # cotas sobre el 2º peldaño
    ya = y0 - b
    cota(msp, T(ya - b, 2 * h), T(ya, 2 * h), K(2), "huella %s" % f2(b, 3))
    cota(msp, T(ya, h), T(ya, 2 * h), -K(4), "contrahuella %s" % f2(h, 4))
    lamina.txt(msp, "%d contrahuellas en total (rev. H); 2h + b = %s m" % (
        sum(f_["steps"] for f_ in ESCALERA["flights"]) + 1, f2(2 * h + b, 3)), T(r[0], 1.10), K(2.0))
    lamina.txt(msp, "Sin veredicto: los umbrales OGUC de escaleras están sin transcribir.", T(r[0], 1.04), K(1.8), color=8)
    nota(msp, "Peldaños según el modelo (Arch Stairs).\nTerminación de huella: por definir", T(y0 - 3.5 * b, 3.5 * h), T(r[0] + 0.03, 0.20), izq=False)
    return T


def d5_ventana(msp, o):
    r = (-0.45, 0.65, 0.65, 2.55)
    T = detalle(msp, "corte_bb", r, o, factor=0.5)
    s, hd = VENTANA["sill"], VENTANA["head"]
    cota(msp, T(0.40, s), T(0.40, hd), -K(1.5), "vano %s" % f2(hd - s))
    nivel(msp, T(0.55, s), "alféizar +%s" % f2(s))
    nivel(msp, T(0.55, hd), "dintel +%s" % f2(hd))
    nota(msp, "%s\n(partida 6, propuesta)" % TERM[6]["terminacion"], T(0.10, (s + hd) / 2), T(-0.40, 2.30))
    nota(msp, "Dintel: cadena/dintel de HA\n(por el calculista)", T(0.10, hd + 0.08), T(-0.40, 2.48))
    nota(msp, "Alféizar con pendiente al exterior\ny cortagotera (por definir)", T(-0.02, s), T(-0.40, 0.85))
    return T


def lamina_detalles():
    d = setup_doc()
    for nombre, col, lw in (("A-VIST", 7, 25), ("A-SECC", 8, 50), ("A-NIVEL", 7, 18), ("A-DET-MARCO", 9, 13),
                            ("A-DET-NOTA", 7, 13), ("A-DET-TERM", 2, 13)):
        d.layers.add(nombre, color=col, lineweight=lw)
    d.layers.add("A-DET-ESQ", color=1, linetype="DASHED", lineweight=25)
    msp = d.modelspace()
    fuente_bb = "recorte del corte B-B (Y = %s m), muro poniente" % f2(VISTAS["corte_bb"]["corte"])
    piezas = [
        (d1_alero, (0.85, 2.55), 1, "ALERO, CANAL Y BAJADA", 10, fuente_bb),
        (d2_losa, (3.05, 2.75), 2, "ENCUENTRO MURO - LOSA 2º PISO", 10, fuente_bb),
        (d5_ventana, (5.05, 2.70), 5, "VANO DE VENTANA", 20, "recorte del corte B-B"),
        (d3_zocalo, (0.85, 0.40), 3, "ZÓCALO Y FUNDACIÓN", 10, fuente_bb),
        (d4_escalera, (2.55, 0.95), 4, "ESCALERA, TRAMO 1", 10, "recorte del corte A-A (X = %s m)" % f2(VISTAS["corte_aa"]["corte"])),
    ]
    for fn, o, n, s, e, fu in piezas:
        fn(msp, o)
        titulo(msp, n, s, e, fu, (o[0], o[1] - K(14)))
    lamina.marco_y_vineta(msp, "detalles", [
        "Líneas: recorte de los cortes del modelo FreeCAD. Terminaciones y esquemas en capas aparte.",
        "Materiales: propuestas (terminaciones.json, estructura.json) hasta su confirmación.",
        "Armaduras, cadenas y fundaciones: proyecto de cálculo (ingeniero civil)."])
    lamina.presentacion(d, "detalles")
    return d


def main():
    d = lamina_detalles()
    out = DRAW / "detalles.dxf"
    d.saveas(out)
    print("escrito", out)


if __name__ == "__main__":
    main()
