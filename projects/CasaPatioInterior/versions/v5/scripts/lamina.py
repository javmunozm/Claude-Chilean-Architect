# -*- coding: utf-8 -*-
"""Lámina A2 común a todos los planos de v5: marco, viñeta, numeración, PDF y presentación.

Lo usan make_dxf.py (plantas) y make_views.py (cubierta, elevaciones, cortes). Cada
lámina vive en el espacio modelo del DXF, en metros, con un marco del tamaño del papel
multiplicado por la escala (A2 = 594 x 420 mm; a 1:50 son 29,7 x 21,0 m).

- La viñeta lee el nombre del proyecto, propietario y arquitecto de ../source/proyecto.json
  y la dirección, rol y comuna del site.json del proyecto. Un dato en null se imprime
  "por definir": nunca se inventa.
- La fecha es la del día en que se generó la lámina; la numeración sale de HOJAS.
- El PDF se escribe al tamaño real del papel (594 x 420 mm), así que se puede imprimir
  y medir a la escala que dice la viñeta.
- Cada DXF lleva una presentación "A2 1-N" con la ventana a esa escala.
"""
import datetime
import json
from pathlib import Path

from ezdxf.enums import TextEntityAlignment as AL

VER = Path(__file__).resolve().parents[1]
PROYECTO = json.loads((VER / "source" / "proyecto.json").read_text(encoding="utf-8"))
SITIO = json.loads((VER.parents[1] / "site.json").read_text(encoding="utf-8"))
REVISION = "v5-A"
PAPEL_MM = (594.0, 420.0)          # A2 horizontal

# Juego de láminas, en orden: clave -> (título, esquina inferior izquierda en el modelo, escala)
HOJAS = {
    "planta_p1": ("PLANTA PRIMER PISO", (-4.0, -18.5), 50),
    "planta_p2": ("PLANTA SEGUNDO PISO", (-4.0, -18.5), 50),
    "cubierta": ("PLANTA DE CUBIERTA", (-4.0, -18.5), 50),
    "elevaciones": ("ELEVACIONES", (0.0, 0.0), 100),
    "cortes": ("CORTES A-A Y B-B", (0.0, 0.0), 50),
    "detalles": ("DETALLES CONSTRUCTIVOS", (0.0, 0.0), 10),
}


def tamano(escala):
    """Tamaño del marco en metros de modelo."""
    return PAPEL_MM[0] * escala / 1000.0, PAPEL_MM[1] * escala / 1000.0


def mm(escala, v):
    """v milímetros de papel, en metros de modelo."""
    return v * escala / 1000.0


def numero(clave):
    return list(HOJAS).index(clave) + 1, len(HOJAS)


def dato(v):
    return v if v not in (None, "") else "por definir"


def txt(msp, s, pos, h, layer="A-TEXT", align=AL.LEFT, color=None, rot=0):
    t = msp.add_text(s, height=h, rotation=rot, dxfattribs={"layer": layer, "style": "ARQ"})
    t.set_placement(pos, align=align)
    if isinstance(color, tuple):
        t.rgb = color
    elif color:
        t.dxf.color = color
    return t


def marco_y_vineta(msp, clave, notas=()):
    """Marco del papel, margen y viñeta completa en la esquina inferior derecha."""
    titulo, (x0, y0), esc = HOJAS[clave]
    w, h = tamano(esc)
    k = lambda v: mm(esc, v)  # noqa: E731
    x1, y1 = x0 + w, y0 + h
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": "A-CUAD"})
    m = k(10)
    msp.add_lwpolyline([(x0 + m, y0 + m), (x1 - m, y0 + m), (x1 - m, y1 - m), (x0 + m, y1 - m)],
                       close=True, dxfattribs={"layer": "A-CUAD"})
    # viñeta: 210 x 64 mm. Arriba, las notas a todo el ancho; abajo, los datos del
    # proyecto y, a la derecha, escala, fecha, revisión y número de lámina.
    bx1, by0 = x1 - m, y0 + m
    bx0, by1 = bx1 - k(210), by0 + k(64)
    msp.add_lwpolyline([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], close=True, dxfattribs={"layer": "A-CUAD"})
    yn = by1 - k(24)
    msp.add_line((bx0, yn), (bx1, yn), dxfattribs={"layer": "A-CUAD"})
    c2 = bx1 - k(55)
    msp.add_line((c2, by0), (c2, yn), dxfattribs={"layer": "A-CUAD"})
    n, total = numero(clave)
    generales = ["Cotas y niveles en metros. NPT ±0,00.",
                 "Sin veredicto normativo: umbrales OGUC sin transcribir (INCONCLUSO).",
                 "Norte según el documento rev. G; no hay levantamiento del sitio."]
    yy = by1 - k(4)
    for s_ in list(notas) + generales:
        txt(msp, s_, (bx0 + k(3), yy), k(1.6))
        yy -= k(3.0)
    filas = [
        (titulo, 3.6),
        ("%s — %s, versión %s" % (dato(PROYECTO.get("nombre")), dato(PROYECTO.get("etapa")), VER.name), 1.9),
        ("Propietario: %s" % dato(PROYECTO.get("propietario")), 1.9),
        ("Arquitecto: %s   Registro: %s" % (dato(PROYECTO.get("arquitecto")),
                                            dato(PROYECTO.get("arquitecto_registro"))), 1.9),
        ("Dirección: %s" % dato(SITIO.get("address")), 1.9),
        ("Rol: %s   ·   Comuna: %s" % (dato(SITIO.get("rol")), dato(SITIO.get("comuna"))), 1.9),
    ]
    yy = yn - k(6)
    for s_, hmm in filas:
        txt(msp, s_, (bx0 + k(3), yy), k(hmm))
        yy -= k(7.0 if hmm > 3 else 5.6)
    txt(msp, "Escala 1:%d" % esc, (c2 + k(3), yn - k(6)), k(2.6))
    txt(msp, "Papel A2 (594 x 420 mm)", (c2 + k(3), yn - k(11)), k(1.6))
    txt(msp, "Fecha %s   Rev. %s" % (datetime.date.today().isoformat(), REVISION), (c2 + k(3), yn - k(16)), k(1.7))
    txt(msp, "LÁMINA", (c2 + k(3), yn - k(23)), k(1.8))
    txt(msp, "%d / %d" % (n, total), (c2 + k(3), yn - k(35)), k(7.0))
    return (bx0, by0, bx1, by1)


def presentacion(doc, clave):
    """Presentación 'A2 1-N': una ventana que muestra el marco a la escala de la lámina."""
    _, (x0, y0), esc = HOJAS[clave]
    w, h = tamano(esc)
    nombre = "A2 1-%d" % esc
    lay = doc.layouts.new(nombre)
    lay.page_setup(size=PAPEL_MM, margins=(0, 0, 0, 0), units="mm")
    lay.add_viewport(center=(PAPEL_MM[0] / 2, PAPEL_MM[1] / 2), size=PAPEL_MM,
                     view_center_point=(x0 + w / 2, y0 + h / 2), view_height=h)
    if "Layout1" in doc.layouts:
        doc.layouts.delete("Layout1")


def pdf_pagina(doc, clave, pdf, png=None, dpi_png=60):
    """Página del PDF al tamaño real del papel (y PNG de control, más liviano)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    _, (x0, y0), esc = HOJAS[clave]
    w, h = tamano(esc)
    fig = plt.figure(figsize=(PAPEL_MM[0] / 25.4, PAPEL_MM[1] / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE)
    Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace(), finalize=True)
    # finalize() de ezdxf reduce la figura a ~6,8 x 4,8 pulgadas (medido 2026-10-04): por
    # eso los PDF de v2/v3 salían a 172 x 122 mm. Se devuelve al tamaño real del papel.
    fig.set_size_inches(PAPEL_MM[0] / 25.4, PAPEL_MM[1] / 25.4)
    ax.set_position([0, 0, 1, 1])
    ax.set_xlim(x0, x0 + w)
    ax.set_ylim(y0, y0 + h)
    ax.set_aspect("equal")
    ax.axis("off")
    pdf.savefig(fig)
    if png:
        fig.savefig(png, dpi=dpi_png)
    plt.close(fig)
