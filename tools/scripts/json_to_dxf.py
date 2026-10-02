#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera plantas DXF acotadas y rotuladas desde la especificacion JSON.

Salida en metros, un archivo por nivel. Incluye:
  - muros cortados en los vanos, con contorno grueso y relleno (poche)
  - puertas con hoja y arco de abatimiento; correderas con sus dos hojas
  - ventanas con lineas de alfeizar y doble linea de vidrio
  - codigo de vano (P01, V01...) fuera del muro y cuadro de vanos al costado
  - cotas por cada eje de muro, en dos lineas (parcial y total)
  - rotulo de cada recinto con su superficie declarada
  - escalera con linea de corte: lo que esta sobre el plano de corte, punteado
  - simbolo de norte, cota de nivel y vineta con escala
  - una presentacion (paperspace) A3 con ventana a la escala pedida

Textos y cotas se dimensionan en MILIMETROS DE PAPEL y se convierten a metros de
modelo con la escala de impresion (--escala, por defecto 1:100). Antes las
alturas estaban fijas en 0,14-0,20 m de modelo, que a 1:100 son 1,4-2,0 mm en
papel: por debajo de lo legible. Todos los textos usan el estilo ARQ (Arial
TrueType); antes usaban 'Standard' -> txt.shx, que los visores sin esa fuente
SHX sustituyen por un trazo ilegible.

Capas (apagables por separado en AutoCAD / BricsCAD / QCAD / LibreCAD):
    A-MURO  A-MURO-RELL  A-VANO  A-LOSA  A-ESCA  A-COTA  A-TEXT  A-RECI
    A-SIMB  A-CUAD

Puertas (tools/puertas.py, compartido con versions/vN/scripts/derive_puertas.py):
  - Si el vano declara cómo abre, eso manda:
        "operation": "swing" | "sliding" | "double"
        "hinge":     "start" | "end"   jamba de la bisagra (start = coordenada menor)
        "swing":     +1 | -1           lado hacia el que abre (+1 = hacia +x / +y)
  - Si no, se infiere con las reglas de diseño R1-R9 (abre hacia el recinto y no
    hacia el pasillo, hacia el baño o clóset, bisagra en la esquina, arco libre...).
  - Si el modelo no las trae, se GENERAN (cortando el muro, código marcado con *):
    todo dormitorio lleva puerta propia y todo recinto sin acceso recibe una.
    Escaleras y circulaciones no reciben puerta generada salvo que se pida con
    --puertas-circulacion; --con-puerta PALABRA suma recintos que exigen puerta.
  Los recintos salen de --recintos: con polígono ("neto"/"bruto"/"pts") se usan
  tal cual; con solo un punto de rótulo se derivan del espacio libre entre muros.

Campo opcional en "meta":
    "norte": "-y" | "+y"   hacia donde apunta el norte en planta. Por defecto
                            la convencion del repositorio (+Y sur -> "-y").

Uso:
    python tools/scripts/json_to_dxf.py <planta.json> --outdir <dir> \
        [--recintos <recintos.json>] [--escala 100]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import ezdxf
    from ezdxf import bbox
    from ezdxf.enums import TextEntityAlignment
except ImportError:
    print("error: falta ezdxf. Instalar con: pip install ezdxf", file=sys.stderr)
    raise SystemExit(2)

try:
    from shapely.geometry import Point, Polygon, box
    from shapely.ops import unary_union
except ImportError:
    print("error: falta shapely. Instalar con: pip install shapely", file=sys.stderr)
    raise SystemExit(2)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # tools/
import puertas  # noqa: E402

# Color 7 se dibuja negro sobre fondo blanco y blanco sobre fondo negro: es el
# unico legible en ambos. El amarillo (2) y el cian (4) de la version anterior
# eran casi invisibles sobre fondo blanco.
# (nombre, color ACI, grosor de linea en centesimas de mm, descripcion)
CAPAS = [
    ("A-MURO", 7, 50, "muros cortados: contorno"),
    ("A-MURO-RELL", 253, 0, "muros cortados: relleno (poche)"),
    ("A-VANO", 7, 18, "puertas y ventanas"),
    ("A-LOSA", 8, 13, "contorno de losa"),
    ("A-ESCA", 7, 18, "escalera"),
    ("A-COTA", 1, 13, "cotas"),
    ("A-TEXT", 7, 25, "textos generales"),
    ("A-RECI", 5, 18, "rotulos de recinto"),
    ("A-SIMB", 7, 25, "simbolos: norte, niveles"),
    ("A-CUAD", 7, 13, "cuadro de vanos"),
]

FUENTE = "arial.ttf"
ESTILO = "ARQ"
SEGMENTADO = "ARQ-SEGM"

# Alturas de texto en mm de papel. 2,5 mm es el minimo usual de rotulacion
# tecnica impresa; los titulos van mayores.
MM = {
    "titulo": 4.0,
    "subtitulo": 2.5,
    "recinto": 2.8,
    "area": 2.2,
    "vano": 2.2,
    "cota": 2.2,
    "cuadro": 2.0,
    "nota": 2.2,
    "norte": 4.0,
    "nivel": 2.5,
}

# Plano de corte horizontal de la planta, medido desde el NPT del nivel.
CORTE_PLANTA = 1.20

TOL = 1e-6


class Papel:
    """Convierte milimetros de papel a metros de modelo para una escala 1:N."""

    def __init__(self, escala):
        self.escala = escala

    def __call__(self, mm):
        return mm * self.escala / 1000.0


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


def texto(msp, contenido, punto, altura, capa, centrado=False, alin=None):
    t = msp.add_text(contenido, height=altura,
                     dxfattribs={"layer": capa, "style": ESTILO})
    if alin is not None:
        t.set_placement(punto, align=alin)
    elif centrado:
        t.set_placement(punto, align=TextEntityAlignment.MIDDLE_CENTER)
    else:
        t.set_placement(punto)
    return t


def partir_nombre(nombre, max_chars=12):
    """Parte un rotulo largo en dos lineas por el espacio mas centrado."""
    if len(nombre) <= max_chars or " " not in nombre:
        return [nombre]
    mitad = len(nombre) / 2.0
    cortes = [i for i, c in enumerate(nombre) if c == " "]
    i = min(cortes, key=lambda k: abs(k - mitad))
    return [nombre[:i], nombre[i + 1:]]


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
                                     dimstyle=ESTILO, dxfattribs={"layer": capa})
        else:
            dim = msp.add_linear_dim(base=(base, 0), p1=(base, a), p2=(base, b),
                                     angle=90, dimstyle=ESTILO,
                                     dxfattribs={"layer": capa})
        dim.render()


def simbolo_norte(msp, x, y, p, hacia="-y"):
    """Flecha de norte.

    Convencion del repositorio: +X este, +Y sur, de modo que el NORTE apunta a
    -Y (hacia ABAJO en el dibujo). Un proyecto cuyo JSON use otra orientacion
    lo declara en meta.norte = "+y".
    """
    r = p(9.0)
    s = -1.0 if hacia == "-y" else 1.0
    msp.add_circle((x, y), r, dxfattribs={"layer": "A-SIMB"})
    flecha = [(x, y + s * r * 0.95),
              (x - r * 0.28, y - s * r * 0.5),
              (x, y - s * r * 0.2),
              (x + r * 0.28, y - s * r * 0.5)]
    msp.add_lwpolyline(flecha, close=True, dxfattribs={"layer": "A-SIMB"})
    relleno = msp.add_hatch(color=7, dxfattribs={"layer": "A-SIMB"})
    relleno.paths.add_polyline_path([flecha[0], flecha[1], flecha[2]], is_closed=True)
    texto(msp, "N", (x, y + s * (r + p(4.0))), p(MM["norte"]), "A-SIMB", centrado=True)


def simbolo_nivel(msp, x, y, cota, p):
    """Triangulo de cota de nivel (NPT)."""
    s = p(2.2)
    msp.add_lwpolyline([(x, y), (x - s, y + s * 1.6), (x + s, y + s * 1.6)],
                       close=True, dxfattribs={"layer": "A-SIMB"})
    texto(msp, "NPT %s" % fmt_cota(cota), (x + s * 1.5, y + s * 0.6),
          p(MM["nivel"]), "A-SIMB")


def fmt_m(v, dec=2):
    """Numero con coma decimal, como se rotula en Chile."""
    return ("%.*f" % (dec, v)).replace(".", ",")


def fmt_cota(v):
    return ("%+.2f" % v).replace(".", ",")


def cuadro_vanos(msp, vanos, x, y, p):
    """Tabla de vanos al costado derecho de la planta."""
    if not vanos:
        return
    h = p(3.6)
    anchos = [p(v) for v in (11.0, 28.0, 13.0, 13.0, 19.0)]
    encabezados = ["COD", "TIPO", "ANCHO", "ALTO", "ANTEPECHO"]

    texto(msp, "CUADRO DE VANOS", (x, y + p(3.0)), p(3.0), "A-CUAD")

    filas = [encabezados] + vanos
    total_ancho = sum(anchos)
    n = len(filas)
    y_sup = y
    y_inf = y - n * h

    msp.add_lwpolyline([(x, y_sup), (x + total_ancho, y_sup),
                        (x + total_ancho, y_inf), (x, y_inf)],
                       close=True, dxfattribs={"layer": "A-CUAD"})
    for i in range(1, n):
        yy = y_sup - i * h
        msp.add_line((x, yy), (x + total_ancho, yy),
                     dxfattribs={"layer": "A-CUAD"})

    cx = x
    for a in anchos[:-1]:
        cx += a
        msp.add_line((cx, y_sup), (cx, y_inf), dxfattribs={"layer": "A-CUAD"})

    for i, fila in enumerate(filas):
        yy = y_sup - i * h - h / 2.0
        cx = x
        for j, celda in enumerate(fila):
            texto(msp, str(celda), (cx + p(1.2), yy), p(MM["cuadro"]), "A-CUAD",
                  alin=TextEntityAlignment.MIDDLE_LEFT)
            cx += anchos[j]


def vineta(msp, spec, level_id, cota, x, y, ancho, p, notas):
    """Vineta con titulo, lamina, escala y notas."""
    linea = p(4.6)
    alto = linea * (5 + len(notas)) + p(2.0)
    msp.add_lwpolyline([(x, y), (x + ancho, y), (x + ancho, y + alto), (x, y + alto)],
                       close=True, dxfattribs={"layer": "A-TEXT"})
    meta = spec.get("meta", {})
    titulo = meta.get("titulo", "")
    sub = meta.get("subtitulo", "")
    rev = meta.get("rev", "")

    yy = y + alto - linea
    texto(msp, titulo, (x + p(2.0), yy), p(MM["titulo"]), "A-TEXT")
    yy -= linea
    texto(msp, sub, (x + p(2.0), yy), p(MM["subtitulo"]), "A-TEXT")
    yy -= p(1.6)
    msp.add_line((x, yy), (x + ancho, yy), dxfattribs={"layer": "A-TEXT"})
    yy -= linea
    texto(msp, "PLANTA NIVEL %s   NPT %s m" % (level_id.upper(), fmt_cota(cota)),
          (x + p(2.0), yy), p(3.0), "A-TEXT")
    yy -= linea
    texto(msp, "Escala 1:%d (lamina A3)   Medidas en METROS   Rev. %s"
          % (p.escala, rev), (x + p(2.0), yy), p(MM["nota"]), "A-TEXT")
    for nota in notas:
        yy -= linea
        texto(msp, nota, (x + p(2.0), yy), p(MM["nota"]), "A-TEXT")


# ------------------------------------------------------------------ vanos

class Vano:
    """Geometria local de un vano: eje u a lo largo del muro, v a traves."""

    def __init__(self, o):
        x0, y0, x1, y1 = o["rect"]
        self.o = o
        self.horizontal = (x1 - x0) >= (y1 - y0)
        if self.horizontal:
            self.u0, self.u1, self.v0, self.v1 = x0, x1, y0, y1
        else:
            self.u0, self.u1, self.v0, self.v1 = y0, y1, x0, x1
        self.ancho = self.u1 - self.u0
        self.t = self.v1 - self.v0
        self.vm = (self.v0 + self.v1) / 2.0
        self.um = (self.u0 + self.u1) / 2.0

    def xy(self, u, v):
        return (u, v) if self.horizontal else (v, u)

    def corte(self, holgura=0.02):
        """Poligono que se resta del muro: atraviesa todo el espesor."""
        a = self.xy(self.u0, self.v0 - holgura)
        b = self.xy(self.u1, self.v1 + holgura)
        return box(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))

    def lado_interior(self, huella):
        """+1/-1 si exactamente un lado del vano cae dentro de la huella del
        nivel (vano de fachada); None si ambos o ninguno (vano interior)."""
        d = self.t / 2.0 + 0.30
        dentro_mas = huella.contains(Point(self.xy(self.um, self.vm + d)))
        dentro_menos = huella.contains(Point(self.xy(self.um, self.vm - d)))
        if dentro_mas and not dentro_menos:
            return 1
        if dentro_menos and not dentro_mas:
            return -1
        return None


def linea(msp, a, b, capa="A-VANO", **kw):
    attrs = {"layer": capa}
    attrs.update(kw)
    msp.add_line(a, b, dxfattribs=attrs)


def dibujar_ventana(msp, v):
    for vv in (v.v0, v.v1):                                   # alfeizar en ambas caras
        linea(msp, v.xy(v.u0, vv), v.xy(v.u1, vv))
    for dv in (-0.015, 0.015):                                # vidrio
        linea(msp, v.xy(v.u0, v.vm + dv), v.xy(v.u1, v.vm + dv), lineweight=13)


def dibujar_abertura(msp, v):
    """Vano sin hoja: dintel sobre el plano de corte, en segmentado."""
    for vv in (v.v0, v.v1):
        linea(msp, v.xy(v.u0, vv), v.xy(v.u1, vv), linetype=SEGMENTADO)


def dibujar_corredera(msp, v):
    """Dos hojas paralelas que se traslapan en el centro del vano."""
    e = 0.03
    tras = 0.05
    for (ua, ub, dv) in ((v.u0, v.um + tras, -e), (v.um - tras, v.u1, e)):
        pts = [v.xy(ua, v.vm + dv - e / 2), v.xy(ub, v.vm + dv - e / 2),
               v.xy(ub, v.vm + dv + e / 2), v.xy(ua, v.vm + dv + e / 2)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "A-VANO"})


def dibujar_hojas(msp, dec):
    """Hoja(s) abierta(s) a 90 grados y arco(s) de barrido, según tools/puertas.py."""
    n = dec["normal"]
    for h in dec["hojas"]:
        hx, hy = h["bisagra"]
        r = h["radio"]
        linea(msp, (hx, hy), (hx + n[0] * r, hy + n[1] * r), lineweight=25)
        a0, a1 = h["a0_deg"], h["a1_deg"]
        ini, fin = (a0, a1) if a1 > a0 else (a1, a0)
        msp.add_arc((hx, hy), r, ini % 360.0, fin % 360.0, dxfattribs={"layer": "A-VANO"})


def dibujar_vano(msp, o, cod, dec, huella, p, generada=False):
    """Dibuja el vano y su código. Devuelve la fila del cuadro de vanos."""
    v = Vano(o)
    kind = o["kind"]
    interior = v.lado_interior(huella)
    sill = o.get("sill", 0.0) or 0.0
    head = o.get("head", 0.0) or 0.0
    alto = head - sill

    if kind == "door":
        if dec is None or dec["tipo"] == "corredera":
            dibujar_corredera(msp, v)
            tipo = "Puerta corredera"
            lado_tag = -interior if interior else 1
        else:
            dibujar_hojas(msp, dec)
            tipo = "Puerta doble" if dec["tipo"].startswith("doble") else "Puerta"
            n = dec["normal"]
            lado_swing = 1 if (n[1] if v.horizontal else n[0]) > 0 else -1
            lado_tag = -lado_swing
        if generada:
            tipo += " (generada)"
    elif kind == "window":
        dibujar_ventana(msp, v)
        tipo = "Ventana"
        lado_tag = -interior if interior else 1
    else:
        dibujar_abertura(msp, v)
        tipo = "Vano libre"
        lado_tag = -interior if interior else 1

    # código fuera del muro, del lado opuesto a la hoja (o hacia el exterior)
    d = v.t / 2.0 + p(3.2)
    t = texto(msp, cod + ("*" if generada else ""), v.xy(v.um, v.vm + lado_tag * d),
              p(MM["vano"]), "A-VANO", centrado=True)
    if generada:
        t.dxf.color = 6
    return [cod + ("*" if generada else ""), tipo, fmt_m(v.ancho), fmt_m(alto),
            fmt_m(sill) if kind == "window" else "-"]


def codigos(vanos):
    """P01.., V01.., A01.. en el orden del JSON (el mismo de la versión anterior)."""
    n = {"door": 0, "window": 0}
    out = []
    for o in vanos:
        k = o["kind"] if o["kind"] in n else "open"
        n[k] = n.get(k, 0) + 1
        out.append((o, "%s%02d" % ({"door": "P", "window": "V"}.get(k, "A"), n[k])))
    return out


def recintos_del_nivel(recintos, level_id, huella, polys_muros):
    """Recintos con polígono para tools/puertas.py: del archivo o derivados de los muros."""
    lv = (recintos or {}).get("niveles", {}).get(level_id, {})
    regs = lv.get("recintos", [])
    con_poligono = [r for r in regs if r.get("neto") or r.get("bruto") or r.get("pts")]
    if regs and len(con_poligono) == len(regs):
        return [{"label": r.get("label") or r.get("nombre"),
                 "pts": r.get("neto") or r.get("pts") or r.get("bruto"),
                 "tipo": r.get("tipo")} for r in regs]
    rotulos = [{"nombre": r.get("nombre") or r.get("label"),
                "punto": r.get("punto") or r.get("punto_rotulo"), "tipo": r.get("tipo")}
               for r in regs if (r.get("punto") or r.get("punto_rotulo"))]
    return puertas.regiones_desde_muros(huella, polys_muros, rotulos)


def obstaculos_del_nivel(spec, zl, es_base):
    """Mobiliario del nivel y peldaños pisables (bajo el plano de corte) en la planta baja."""
    obs = []
    for b in spec.get("boxes", []):
        if zl - 0.1 <= b["z"][0] < zl + 2.0:
            x0, x1 = b["x"]
            y0, y1 = b["y"]
            obs.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    if es_base:
        for st in spec.get("stairs", []):
            hu, ch, n = st["tread"], st["riser"], 0
            for fl in st["flights"]:
                x0, x1 = fl["x"]
                for k in range(fl["steps"]):
                    n += 1
                    if n * ch < CORTE_PLANTA:
                        ya = fl["y_start"] + fl["dir"] * k * hu
                        yb = fl["y_start"] + fl["dir"] * (k + 1) * hu
                        obs.append([(x0, min(ya, yb)), (x1, min(ya, yb)), (x1, max(ya, yb)), (x0, max(ya, yb))])
                if fl.get("landing"):
                    n += 1
    return obs


def llegadas_escalera(spec, zl):
    """Puntos donde la escalera llega al nivel zl (fin del último tramo)."""
    pts = []
    for st in spec.get("stairs", []):
        n_alz = sum(f["steps"] for f in st["flights"]) + sum(1 for f in st["flights"] if f.get("landing"))
        if abs(st["base"] + n_alz * st["riser"] - zl) > 0.05:
            continue
        f = st["flights"][-1]
        x0, x1 = f["x"]
        y_fin = f["y_start"] + f["dir"] * f["steps"] * st["tread"]
        pts.append(((x0 + x1) / 2, y_fin + f["dir"] * 0.3))
    return pts


def vano_para_puertas(o, cod):
    v = Vano(o)
    cx, cy = v.xy(v.um, v.vm)
    out = {"codigo": cod, "tipo": o["kind"] if o["kind"] in ("door", "window") else "open",
           "cx": cx, "cy": cy, "horizontal": v.horizontal, "largo": v.ancho,
           "espesor_muro": v.t, "antepecho": o.get("sill", 0.0) or 0.0,
           "dintel": o.get("head", 0.0) or 0.0}
    for k in ("operation", "hinge", "swing"):
        if k in o:
            out[k] = o[k]
    return out


# ------------------------------------------------------------------ escalera

def dibujar_escalera(msp, st, zl, p):
    """Escalera vista desde el nivel zl.

    En el nivel de arranque, los peldanos cuya cara superior queda sobre el
    plano de corte (NPT + 1,20 m) se dibujan en segmentado: estan por encima del
    corte. En el nivel de llegada se ve entera, por el vacio, y se rotula BAJA.
    """
    hu, ch = st["tread"], st["riser"]
    base = st["base"]
    n_alz = sum(f["steps"] for f in st["flights"]) + \
        sum(1 for f in st["flights"] if f.get("landing"))
    llegada = base + n_alz * ch
    if abs(zl - base) < 0.05:
        sube = True
    elif abs(zl - llegada) < 0.05:
        sube = False
    else:
        return

    def attrs(z_sup):
        a = {"layer": "A-ESCA"}
        if sube and z_sup - base > CORTE_PLANTA:
            a.update(linetype=SEGMENTADO)
        return a

    n = 0
    for fl in st["flights"]:
        x0, x1 = fl["x"]
        y = fl["y_start"]
        d = fl["dir"]
        for k in range(fl["steps"]):
            n += 1
            ya = y + d * k * hu
            yb = y + d * (k + 1) * hu
            msp.add_lwpolyline(
                [(x0, min(ya, yb)), (x1, min(ya, yb)),
                 (x1, max(ya, yb)), (x0, max(ya, yb))],
                close=True, dxfattribs=attrs(base + n * ch))
        if fl.get("landing"):
            n += 1
            lx0, ly0, lx1, ly1 = fl["landing"]
            msp.add_lwpolyline([(lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1)],
                               close=True, dxfattribs=attrs(base + n * ch))
        y_fin = y + d * fl["steps"] * hu
        xm = (x0 + x1) / 2
        msp.add_line((xm, y), (xm, y_fin), dxfattribs={"layer": "A-ESCA"})
        s = p(1.2) * (1 if d > 0 else -1)
        msp.add_lwpolyline(
            [(xm, y_fin), (xm - p(1.0), y_fin - s * 1.6), (xm + p(1.0), y_fin - s * 1.6)],
            close=True, dxfattribs={"layer": "A-ESCA"})

    # rotulo en dos lineas sobre el primer descanso (o junto al arranque)
    f0 = st["flights"][0]
    if f0.get("landing"):
        lx0, ly0, lx1, ly1 = f0["landing"]
        cx, cy = (lx0 + lx1) / 2.0, (ly0 + ly1) / 2.0
    else:
        cx, cy = (f0["x"][0] + f0["x"][1]) / 2.0, f0["y_start"]
    h = p(MM["vano"])
    texto(msp, "SUBE" if sube else "BAJA", (cx, cy + h * 0.7), h, "A-ESCA", centrado=True)
    texto(msp, "%d x %s" % (n_alz, fmt_m(ch, 3)), (cx, cy - h * 0.7), h, "A-ESCA",
          centrado=True)


# ------------------------------------------------------------------ documento

def nuevo_documento(p):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6      # metros
    doc.header["$MEASUREMENT"] = 1   # metrico
    doc.header["$LWDISPLAY"] = 1     # mostrar grosores de linea
    for nombre, color, grosor, descr in CAPAS:
        capa = doc.layers.add(nombre, color=color)
        if grosor:
            capa.dxf.lineweight = grosor
        capa.description = descr

    doc.styles.add(ESTILO, font=FUENTE)

    # Segmentado propio, definido en mm de papel: trazo 3 mm, hueco 1 mm. Los
    # tipos DASHED de fabrica estan en pulgadas y a esta escala sus huecos
    # quedaban por debajo de lo que un visor dibuja, y salian continuos.
    doc.linetypes.add(SEGMENTADO, pattern=[p(4.0), p(3.0), -p(1.0)],
                      description="Segmentado ARQ __ __ __")

    # Estilo de cota propio, legible a la escala de impresion.
    # dimlfac=1 es imprescindible: el estilo por defecto de ezdxf escala x100 y
    # las cotas saldrian en centimetros sobre un dibujo que esta en metros.
    ds = doc.dimstyles.new(ESTILO)
    ds.dxf.dimtxsty = ESTILO
    ds.dxf.dimlfac = 1.0
    ds.dxf.dimscale = 1.0
    ds.dxf.dimtxt = p(MM["cota"])
    ds.dxf.dimasz = p(1.8)
    ds.dxf.dimexe = p(1.2)
    ds.dxf.dimexo = p(1.0)
    ds.dxf.dimgap = p(0.8)
    ds.dxf.dimdec = 2
    ds.dxf.dimdsep = ord(",")        # coma decimal
    ds.dxf.dimtad = 1                # texto sobre la linea de cota
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    ds.dxf.dimzin = 0                # conservar ceros: 0,70 y no ,7
    ds.dxf.dimclrd = 1
    ds.dxf.dimclre = 1
    ds.dxf.dimclrt = 1
    ds.set_arrows(blk=ezdxf.ARROWS.architectural_tick)
    doc.header["$DIMSTYLE"] = ESTILO
    return doc


def presentacion_a3(doc, p, nombre):
    """Lamina A3 apaisada con una ventana a escala 1:N sobre todo el modelo."""
    msp = doc.modelspace()
    ext = bbox.extents(msp)
    if not ext.has_data:
        return None
    ancho_m = ext.size.x
    alto_m = ext.size.y
    papel_w, papel_h, margen = 420.0, 297.0, 10.0
    factor = 1000.0 / p.escala               # mm de papel por metro de modelo
    vp_w = min(ancho_m * factor + 10.0, papel_w - 2 * margen)
    vp_h = min(alto_m * factor + 10.0, papel_h - 2 * margen)
    cabe = ancho_m * factor <= papel_w - 2 * margen and alto_m * factor <= papel_h - 2 * margen

    lay = doc.layouts.new(nombre)
    lay.page_setup(size=(papel_w, papel_h), margins=(0, 0, 0, 0), units="mm")
    lay.add_lwpolyline([(margen, margen), (papel_w - margen, margen),
                        (papel_w - margen, papel_h - margen), (margen, papel_h - margen)],
                       close=True, dxfattribs={"layer": "A-TEXT", "lineweight": 50})
    lay.add_viewport(center=(papel_w / 2, papel_h / 2), size=(vp_w, vp_h),
                     view_center_point=ext.center, view_height=vp_h / factor)
    if "Layout1" in doc.layouts:          # presentacion vacia que crea ezdxf
        doc.layouts.delete("Layout1")
    return cabe


def draw_level(spec, level_id, path, recintos=None, escala=100, politica=None):
    p = Papel(escala)
    doc = nuevo_documento(p)
    msp = doc.modelspace()

    niveles = {l["id"]: l["z"] for l in spec["levels"]}
    zl = niveles[level_id]
    bx0, by0, bx1, by1 = spec["bbox"]

    # ---- losa (y huella del nivel, para saber que lado de un vano es exterior)
    rects_losa = []
    for s in spec.get("slabs", []):
        if abs(s["z"] - zl) > TOL:
            continue
        for x0, y0, x1, y1 in s["rects"]:
            msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                               close=True, dxfattribs={"layer": "A-LOSA"})
            rects_losa.append(box(x0, y0, x1, y1))
    huella = unary_union(rects_losa) if rects_losa else Polygon()

    # ---- puertas: abatimiento indicado o inferido, y puertas que faltan (tools/puertas.py)
    polys = [Polygon(wall_polygon(w)) for w in spec["walls"]
             if w["level"] == level_id and wall_polygon(w)]
    vanos = [o for o in spec.get("openings", []) if o["level"] == level_id]
    con_cod = codigos(vanos)
    es_base = abs(zl - min(niveles.values())) < 1e-6
    recs = recintos_del_nivel(recintos, level_id, huella, [list(p.exterior.coords)[:-1] for p in polys])
    decs, sin_acceso, residuales = puertas.resolver_nivel(
        recs, [list(p.exterior.coords)[:-1] for p in polys],
        [vano_para_puertas(o, c) for o, c in con_cod],
        obstaculos_del_nivel(spec, zl, es_base), level_id, es_planta_baja=es_base,
        inicio=llegadas_escalera(spec, zl), politica=politica)
    dec_por_cod = {d["codigo"]: d for d in decs if not d.get("generada")}
    generadas = [d for d in decs if d.get("generada")]
    vanos_gen = []
    for d in generadas:
        g = d["geometria"]
        hx, hy = (g["largo"] / 2, g["espesor_muro"] / 2) if g["horizontal"] else (g["espesor_muro"] / 2, g["largo"] / 2)
        vanos_gen.append(({"level": level_id, "kind": "door", "sill": 0.0, "head": g["dintel"],
                           "rect": [g["cx"] - hx, g["cy"] - hy, g["cx"] + hx, g["cy"] + hy]}, d))

    # ---- muros: union de solidos menos los vanos, con contorno y relleno
    muros = unary_union(polys)
    if vanos or vanos_gen:
        muros = muros.difference(unary_union([Vano(o).corte() for o in vanos + [o for o, _ in vanos_gen]]))
    piezas = getattr(muros, "geoms", [muros])
    for pz in piezas:
        if pz.is_empty:
            continue
        anillos = [pz.exterior] + list(pz.interiors)
        relleno = msp.add_hatch(color=253, dxfattribs={"layer": "A-MURO-RELL"})
        for k, anillo in enumerate(anillos):
            pts = list(anillo.coords)[:-1]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "A-MURO"})
            relleno.paths.add_polyline_path(
                pts, is_closed=True,
                flags=ezdxf.const.BOUNDARY_PATH_EXTERNAL if k == 0
                else ezdxf.const.BOUNDARY_PATH_DEFAULT)
    n_muros = len(polys)

    # ---- vanos con simbolo y codigo
    vanos_tabla = []
    hay_inferido = False
    for o, cod in con_cod:
        dec = dec_por_cod.get(cod)
        if dec is not None and not dec.get("regla", "").startswith("indicado"):
            hay_inferido = True
        vanos_tabla.append(dibujar_vano(msp, o, cod, dec, huella, p))
    for o, d in vanos_gen:
        vanos_tabla.append(dibujar_vano(msp, o, d["codigo"], d, huella, p, generada=True))

    # ---- escalera
    for st in spec.get("stairs", []):
        dibujar_escalera(msp, st, zl, p)

    # ---- rotulos de recinto
    n_rec = 0
    if recintos:
        lv = recintos.get("niveles", {}).get(level_id)
        if lv:
            for r in lv.get("recintos", []):
                pt = r.get("punto") or r.get("punto_rotulo")
                nombre = r.get("nombre") or r.get("label")
                if not pt or not nombre:
                    continue
                px, py = pt
                lineas = partir_nombre(nombre.upper())
                hn = p(MM["recinto"])
                paso = hn * 1.35
                area = r.get("area_doc_m2")
                total = len(lineas) + (1 if area is not None else 0)
                y_top = py + (total - 1) * paso / 2.0
                for i, ln in enumerate(lineas):
                    texto(msp, ln, (px, y_top - i * paso), hn, "A-RECI", centrado=True)
                if area is not None:
                    marca = "" if r.get("_area_verificada") else " (s/doc)"
                    texto(msp, "%s m2%s" % (fmt_m(area), marca),
                          (px, y_top - len(lineas) * paso), p(MM["area"]),
                          "A-RECI", centrado=True)
                n_rec += 1

    # ---- cotas por eje
    xs, ys = ejes_de_muro(spec, level_id)
    xs_f = filtrar_proximos([v for v in xs if bx0 - 0.5 <= v <= bx1 + 0.5])
    ys_f = filtrar_proximos([v for v in ys if by0 - 0.5 <= v <= by1 + 0.5])

    sep = p(8.0)
    acotar_eje(msp, xs_f, by0 - sep, horizontal=True)
    acotar_eje(msp, ys_f, bx0 - sep, horizontal=False)
    dim = msp.add_linear_dim(base=(0, by0 - 2 * sep), p1=(bx0, by0), p2=(bx1, by0),
                             dimstyle=ESTILO, dxfattribs={"layer": "A-COTA"})
    dim.render()
    dim = msp.add_linear_dim(base=(bx0 - 2 * sep, 0), p1=(bx0, by0), p2=(bx0, by1),
                             angle=90, dimstyle=ESTILO, dxfattribs={"layer": "A-COTA"})
    dim.render()

    # ---- simbolos, cuadro, notas y vineta
    norte = spec.get("meta", {}).get("norte", "-y")
    x_cuadro = bx1 + p(15.0)
    simbolo_norte(msp, x_cuadro + p(12.0), by1 - p(12.0), p, norte)
    simbolo_nivel(msp, bx0 + p(4.0), by1 + p(3.0), zl, p)
    cuadro_vanos(msp, vanos_tabla, x_cuadro, by1 - p(32.0), p)

    notas = ["Cotas a cara de muro. VERIFICAR EN OBRA ANTES DE EJECUTAR."]
    if recintos:
        notas.append("(s/doc) = superficie declarada en el documento, no medida.")
    if hay_inferido:
        notas.append("Abatimiento no indicado en el modelo: inferido con reglas de diseno "
                     "R1-R9 (tools/puertas.py), no normativo.")
    if generadas:
        notas.append("* Puerta generada, no indicada en el modelo (%s)."
                     % ", ".join(d["conecta"][0] for d in generadas))
    if sin_acceso:
        notas.append("SIN ACCESO POSIBLE: %s" % ", ".join(sin_acceso))
    for r in residuales:
        notas.append("AVISO " + r)
    vineta(msp, spec, level_id, zl, bx0 - 2 * sep, by1 + p(10.0),
           (bx1 - bx0) + 2 * sep, p, notas)

    cabe = presentacion_a3(doc, p, "A3 1-%d" % escala)
    doc.saveas(path)
    return n_muros, len(vanos_tabla), n_rec, cabe, decs, sin_acceso, residuales


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--recintos")
    ap.add_argument("--escala", type=int, default=100,
                    help="escala de impresion 1:N (por defecto 100)")
    puertas.agregar_opciones(ap)
    args = ap.parse_args(argv)
    politica = puertas.politica_de_args(args)

    spec = json.load(open(args.spec, encoding="utf-8"))
    recintos = None
    if args.recintos and Path(args.recintos).exists():
        recintos = json.load(open(args.recintos, encoding="utf-8"))

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    fallo = False

    for lvl in spec["levels"]:
        path = out / ("planta_%s.dxf" % lvl["id"])
        m, v, r, cabe, decs, sin, resid = draw_level(spec, lvl["id"], str(path), recintos, args.escala,
                                             politica)
        aviso = "" if cabe else "  AVISO: no cabe en A3 a 1:%d" % args.escala
        print("%s  (%d muros, %d vanos, %d recintos rotulados)%s"
              % (path, m, v, r, aviso))
        for d in decs:
            if d["tipo"] == "corredera":
                print("    %s corredera | %s" % (d["codigo"], d["regla"]))
            else:
                print("    %s%s abre hacia %s | %s%s" % (
                    d["codigo"], "*" if d.get("generada") else "", d["abre_hacia"], d["regla"],
                    " | ADVERTENCIA" if "advertencia" in d else ""))
        if sin:
            print("    SIN ACCESO POSIBLE:", ", ".join(sin))
            fallo = True
        for x in resid:
            print("    AVISO:", x)
    return 1 if fallo else 0


if __name__ == "__main__":
    sys.exit(main())
