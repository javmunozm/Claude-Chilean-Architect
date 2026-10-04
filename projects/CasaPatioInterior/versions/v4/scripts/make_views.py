# -*- coding: utf-8 -*-
"""Láminas de cubierta, elevaciones y cortes, y el PDF del juego completo (5 láminas).

    python make_views.py         (intérprete del sistema: ezdxf, matplotlib)

Entradas:  v4/calcs/views_data.json        export_views.py (proyección del FCStd)
           ../v0/source/casa_rev_h.json    cubiertas (pendientes) y niveles
           v4/exports/drawings/planta_p*.dxf  make_dxf.py (se corre antes)
Salidas:   v4/exports/drawings/cubierta.dxf, elevaciones.dxf, cortes.dxf (+ PNG de control)
           v4/exports/planos_v4.pdf        las 5 láminas, cada página a tamaño A2 real

Las líneas salen del modelo (TechDraw.projectEx, sin líneas ocultas); este script solo
las ubica en la lámina y agrega rótulos que también salen de datos: niveles del JSON,
pendientes calculadas de las cubiertas (z de cumbrera y alero, x de referencia).
"""
import json
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment as AL
from matplotlib.backends.backend_pdf import PdfPages

import lamina
from make_dxf import draw_north, setup_doc

VER = Path(__file__).resolve().parents[1]
VISTAS = json.loads((VER / "calcs" / "views_data.json").read_text(encoding="utf-8"))["vistas"]
SPEC = json.loads((VER.parent / "v0" / "source" / "casa_rev_h.json").read_text(encoding="utf-8"))
DRAW = VER / "exports" / "drawings"
YOFF = 14.0                                   # y del JSON -> Y del modelo (Y = y - 14)
NIVELES = {l["id"]: l["z"] for l in SPEC["levels"]}
Z_TERRENO = SPEC.get("ground", {}).get("z", 0.0)


def nuevo_doc():
    d = setup_doc()
    for nombre, col, lw in (("A-VIST", 7, 25), ("A-SECC", 8, 50), ("A-TERR", 7, 50),
                            ("A-NIVEL", 7, 18), ("A-CUB", 5, 25)):
        d.layers.add(nombre, color=col, lineweight=lw)
    return d


def vista(msp, clave, du, dv):
    """Segmentos visibles y poché de una vista, trasladados (du, dv)."""
    v = VISTAS[clave]
    for p in v["poche"]:
        h = msp.add_hatch(color=250, dxfattribs={"layer": "A-SECC"})
        h.paths.add_polyline_path([(x + du, y + dv) for x, y in p], is_closed=True)
    for a, b, c, e in v["segmentos"]:
        msp.add_line((a + du, b + dv), (c + du, e + dv), dxfattribs={"layer": "A-VIST"})
    return v["bbox"]


def nivel(msp, x, z, dv, rotulo, esc):
    """Marca de nivel (triángulo + texto) a la derecha de una vista."""
    k = lambda mm: lamina.mm(esc, mm)  # noqa: E731
    y = z + dv
    msp.add_line((x, y), (x + k(14), y), dxfattribs={"layer": "A-NIVEL"})
    msp.add_lwpolyline([(x + k(2), y), (x + k(4), y + k(2.5)), (x, y + k(2.5))], close=True,
                       dxfattribs={"layer": "A-NIVEL"})
    lamina.txt(msp, rotulo, (x + k(5), y + k(0.8)), k(2.0), layer="A-NIVEL")


def terreno(msp, u0, u1, dv):
    y = Z_TERRENO + dv
    msp.add_line((u0 - 0.8, y), (u1 + 0.8, y), dxfattribs={"layer": "A-TERR"})


def niveles_de(clave):
    top = VISTAS[clave]["bbox"][3]
    out = [(0.0, "NPT ±0,00"), (NIVELES["p2"], "NPT +%s" % ("%.2f" % NIVELES["p2"]).replace(".", ","))]
    out.append((top, "+%s" % ("%.2f" % top).replace(".", ",")))
    return out


def titulo_vista(msp, s, pos, esc, align=AL.LEFT):
    lamina.txt(msp, s, pos, lamina.mm(esc, 4.0), align=align)
    lamina.txt(msp, "Escala 1:%d" % esc, (pos[0], pos[1] - lamina.mm(esc, 5.5)), lamina.mm(esc, 2.2),
               align=align, color=8)


# ------------------------------------------------------------------ láminas

def lamina_cubierta():
    d = nuevo_doc()
    msp = d.modelspace()
    vista(msp, "cubierta", 0.0, 0.0)            # mismo marco que las plantas: sin traslado
    esc = 50
    k = lambda mm: lamina.mm(esc, mm)  # noqa: E731
    for r in SPEC["roofs"]:
        if r["type"] == "gable":
            a, b = r["x_ref"]
            rx = r["ridge_x"]
            pend = (r["ridge_z"] - r["eave_z"]) / (rx - a)
            pend2 = (r["ridge_z"] - r["eave_z"]) / (b - rx)
            y = 2.0 - YOFF                         # banda sur, lejos del patio
            for x0, x1, p in ((rx - 0.4, a + 1.2, pend), (rx + 0.4, b - 1.2, pend2)):
                flecha(msp, (x0, y), (x1, y), "%s %%" % ("%.1f" % (p * 100)).replace(".", ","), esc)
            lamina.txt(msp, "Cumbrera +%s" % ("%.2f" % r["ridge_z"]).replace(".", ","),
                       (rx + k(2), 0.3 - YOFF + 13.0), k(2.2), rot=90, layer="A-CUB")
        else:
            (x0, z0), (x1, z1) = r["from"], r["to"]
            p = (z0 - z1) / (x1 - x0)
            y = (r["y"][0] + r["y"][1]) / 2 - YOFF
            flecha(msp, (x0 + 0.8, y), (x1 - 0.8, y), "%s %%" % ("%.1f" % (p * 100)).replace(".", ","), esc)
            lamina.txt(msp, "Alero +%s" % ("%.2f" % z1).replace(".", ","), (x1 - 0.3, y - 1.2), k(2.0),
                       align=AL.RIGHT, layer="A-CUB")
    draw_north(msp, 14.85, 1.1)
    titulo_vista(msp, "PLANTA DE CUBIERTA", (4.5, -14.0 - 3.0), esc, AL.MIDDLE_CENTER)
    lamina.marco_y_vineta(msp, "cubierta", [
        "Líneas proyectadas del modelo FreeCAD (vista superior, sin líneas ocultas).",
        "Flechas: sentido de escurrimiento; pendiente calculada de cumbrera y alero.",
        "Canales y bajadas: no están en el modelo; no se dibujan."])
    lamina.presentacion(d, "cubierta")
    return d


def flecha(msp, a, b, rotulo, esc):
    k = lambda mm: lamina.mm(esc, mm)  # noqa: E731
    msp.add_line(a, b, dxfattribs={"layer": "A-CUB"})
    ux = 1.0 if b[0] > a[0] else -1.0
    msp.add_solid([b, (b[0] - ux * k(5), b[1] + k(1.6)), (b[0] - ux * k(5), b[1] - k(1.6))],
                  dxfattribs={"layer": "A-CUB"})
    lamina.txt(msp, rotulo, ((a[0] + b[0]) / 2, a[1] + k(2.5)), k(2.6), align=AL.BOTTOM_CENTER, layer="A-CUB")


def lamina_elevaciones():
    d = nuevo_doc()
    msp = d.modelspace()
    esc = 100
    pos = {"elev_sur": (3.0, 25.0), "elev_norte": (32.0, 25.0),
           "elev_oriente": (3.0, 11.0), "elev_poniente": (32.0, 11.0)}
    for clave, (x, y) in pos.items():
        u0, v0, u1, v1 = VISTAS[clave]["bbox"]
        du = x - u0
        vista(msp, clave, du, y)
        terreno(msp, u0 + du, u1 + du, y)
        for z, rot in niveles_de(clave):
            nivel(msp, u1 + du + 0.6, z, y, rot, esc)
        titulo_vista(msp, VISTAS[clave]["titulo"], (u0 + du, y - 1.6), esc)
    lamina.marco_y_vineta(msp, "elevaciones", [
        "Elevaciones proyectadas del modelo FreeCAD, sin líneas ocultas.",
        "Terreno a %s (dato del JSON); sin levantamiento del sitio." % ("%+.2f" % Z_TERRENO).replace(".", ","),
        "Terminaciones y materiales: no están en el modelo (ver EETT)."])
    lamina.presentacion(d, "elevaciones")
    return d


def lamina_cortes():
    d = nuevo_doc()
    msp = d.modelspace()
    esc = 50
    pos = {"corte_aa": (2.0, 13.4), "corte_bb": (2.0, 5.0)}
    for clave, (x, y) in pos.items():
        u0, v0, u1, v1 = VISTAS[clave]["bbox"]
        du = x - u0
        vista(msp, clave, du, y)
        terreno(msp, u0 + du, u1 + du, y)
        for z, rot in niveles_de(clave):
            nivel(msp, u1 + du + 0.4, z, y, rot, esc)
        plano = "X = %s m, mirando al poniente" if clave == "corte_aa" else "Y = %s m, mirando al norte"
        titulo_vista(msp, VISTAS[clave]["titulo"], (u1 + du + 3.4, y + 3.0), esc)
        lamina.txt(msp, "Plano " + plano % ("%.2f" % VISTAS[clave]["corte"]).replace(".", ","),
                   (u1 + du + 3.4, y + 1.9), lamina.mm(esc, 2.0), color=8)
    lamina.marco_y_vineta(msp, "cortes", [
        "Cortes del modelo FreeCAD; en gris, lo que corta el plano (poché).",
        "Ubicación de A-A y B-B: líneas de corte en las plantas.",
        "Holgura de escalera 1,259 m: hallazgo abierto (README de v2)."])
    lamina.presentacion(d, "cortes")
    return d


def main():
    nuevas = {"cubierta": lamina_cubierta(), "elevaciones": lamina_elevaciones(), "cortes": lamina_cortes()}
    for clave, d in nuevas.items():
        d.saveas(DRAW / (clave + ".dxf"))
        print("escrito", DRAW / (clave + ".dxf"))
    pdf_path = VER / "exports" / ("planos_%s.pdf" % VER.name)
    with PdfPages(pdf_path) as pdf:
        for clave in lamina.HOJAS:
            dxf = DRAW / (clave + ".dxf")
            if not dxf.exists():
                raise SystemExit("falta %s: correr make_dxf.py antes" % dxf)
            lamina.pdf_pagina(ezdxf.readfile(dxf), clave, pdf, png=DRAW / (clave + ".png"))
    print("escrito", pdf_path, "(%d láminas A2)" % len(lamina.HOJAS))


if __name__ == "__main__":
    main()
