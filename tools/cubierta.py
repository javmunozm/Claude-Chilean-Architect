# -*- coding: utf-8 -*-
"""Geometría de cubiertas y cierres bajo cubierta, en Python puro.

Lo usan los dos constructores 3D del repositorio, que antes tenían cada uno su propia
versión (y sus propios errores):

    tools/scripts/blender_build.py                     (Blender, proyectos JSON)
    projects/<P>/versions/vN/scripts/build_model.py  (FreeCAD, objetos Arch)

No importa bpy, FreeCAD ni shapely: corre dentro de cualquiera de los tres
intérpretes del repositorio (docs/system.md). Devuelve mallas como listas de vértices
(x, y, z) en metros, en el marco del JSON de planta, y caras como listas de índices,
orientadas hacia afuera. Cada malla es un sólido CERRADO: cada arista la comparten
exactamente dos caras (se comprueba en `es_cerrada`).

Qué resuelve, y por qué:

1. Un faldón por banda dejaba caras internas entre bandas vecinas y un sólido abierto
   (FreeCAD v2: 25 aristas sin pareja en la cubierta). Aquí toda la cubierta de un
   tipo es UN sólido: las bandas se funden sobre una grilla común y solo quedan las
   caras del contorno.
2. La pendiente sale de x_ref (bordes de alero), no de los bordes de cada banda.
   Convención del JSON: eave_z / ridge_z / from / to son cotas de la cara SUPERIOR y
   el espesor 't' cuelga hacia abajo.
3. Bajo un borde de cubierta recortado (junto a un patio) el muro termina en la
   coronación y la cubierta pasa por encima: quedaba un triángulo abierto al
   entretecho. `cierres_bajo_cubierta` levanta esos muros hasta la cara inferior de
   la cubierta.
4. `diagnostico` revisa los DATOS antes de construir: losa sin nada encima, o muro
   de fachada que la cubierta no alcanza a cubrir. Un dato que deja un sector
   descubierto se informa; no se tapa en silencio inventando una cubierta.
5. `muros_ajustados` resuelve los encuentros: un muro que remata dentro de otro se
   acorta hasta la cara de ese otro, y un muro tapado por una losa termina en la cara
   inferior de la losa. Sin esto dos sólidos ocupan el mismo lugar y sus caras
   coinciden (medido en v2: 26 m2 muro/muro y 20 m2 losa/muro), lo que en pantalla
   se ve como parpadeo o franjas negras. No cambia los datos del JSON.
"""
from __future__ import annotations

import math

EPS = 1e-9


# ------------------------------------------------------------------ cubierta

def z_cubierta(r, x):
    """Cota de la cara SUPERIOR de la cubierta r en la abscisa x."""
    if r.get("type") == "gable":
        a, b = r["x_ref"]
        rx, ez, rz = r["ridge_x"], r["eave_z"], r["ridge_z"]
        if x <= rx:
            return ez + (x - a) / (rx - a) * (rz - ez)
        return ez + (b - x) / (b - rx) * (rz - ez)
    (x0, z0), (x1, z1) = r["from"], r["to"]
    return z0 + (x - x0) / (x1 - x0) * (z1 - z0)


def espesor(r):
    return r.get("t", 0.22 if r.get("type") == "gable" else 0.18)


def rects_cubierta(r):
    """Rectángulos (x0, y0, x1, y1) que cubre la cubierta en planta."""
    if r.get("type") == "gable":
        return [(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                for y0, y1, x0, x1 in r.get("bands", [])]
    (x0, _), (x1, _) = r["from"], r["to"]
    y0, y1 = r["y"]
    return [(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))]


def en_rects(rects, x, y, tol=1e-6):
    return any(x0 - tol <= x <= x1 + tol and y0 - tol <= y <= y1 + tol
               for x0, y0, x1, y1 in rects)


def _normal(P):
    """Normal (sin normalizar) de un polígono plano por el método de Newell."""
    nx = ny = nz = 0.0
    n = len(P)
    for i in range(n):
        x1, y1, z1 = P[i]
        x2, y2, z2 = P[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return nx, ny, nz


class Malla:
    """Vértices compartidos por clave + caras poligonales orientadas hacia afuera."""

    def __init__(self, nombre):
        self.nombre = nombre
        self.verts = []
        self.caras = []
        self._idx = {}
        self.info = {}

    def v(self, x, y, z):
        k = (round(x, 6), round(y, 6), round(z, 6))
        i = self._idx.get(k)
        if i is None:
            i = len(self.verts)
            self._idx[k] = i
            self.verts.append((float(x), float(y), float(z)))
        return i

    def cara(self, idx, afuera):
        """Agrega una cara; la invierte si su normal no apunta al vector `afuera`."""
        P = [self.verts[i] for i in idx]
        n = _normal(P)
        if n[0] * afuera[0] + n[1] * afuera[1] + n[2] * afuera[2] < 0:
            idx = list(reversed(idx))
        self.caras.append(list(idx))

    def como_dict(self):
        d = {"nombre": self.nombre, "verts": self.verts, "caras": self.caras}
        d.update(self.info)
        return d


def _grilla(rects, cortes_x=(), extra=()):
    """Celdas de la grilla común a `rects` (y a los cortes de `extra`), y cuáles cubre `rects`."""
    xs = sorted({v for x0, _, x1, _ in list(rects) + list(extra) for v in (x0, x1)} | set(cortes_x))
    ys = sorted({v for _, y0, _, y1 in list(rects) + list(extra) for v in (y0, y1)})
    cub = {}
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            cub[(i, j)] = en_rects(rects, cx, cy, tol=-1e-9)
    return xs, ys, cub


def malla_cubierta(r, nombre="Cubierta", excluir=()):
    """Sólido cerrado de toda la cubierta r (todas sus bandas fundidas).

    `excluir`: rectángulos que la cubierta NO ocupa, porque un muro más alto la
    atraviesa ahí (ver `atraviesan`). Sin esto el faldón y el muro ocupan el mismo
    lugar y sus caras coinciden: en pantalla parpadean.
    """
    rects = rects_cubierta(r)
    t = espesor(r)
    cortes = [r["ridge_x"]] if r.get("type") == "gable" else []
    xs, ys, cub = _grilla(rects, [c for c in cortes
                                  if min(x[0] for x in rects) < c < max(x[2] for x in rects)],
                          extra=excluir)
    for (i, j) in list(cub):
        cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
        if cub[(i, j)] and en_rects(excluir, cx, cy, tol=-1e-9):
            cub[(i, j)] = False
    m = Malla(nombre)

    def vs(i, j):
        return m.v(xs[i], ys[j], z_cubierta(r, xs[i]))

    def vi(i, j):
        return m.v(xs[i], ys[j], z_cubierta(r, xs[i]) - t)

    nx, ny = len(xs) - 1, len(ys) - 1
    for (i, j), ok in cub.items():
        if not ok:
            continue
        m.cara([vs(i, j), vs(i + 1, j), vs(i + 1, j + 1), vs(i, j + 1)], (0, 0, 1))
        m.cara([vi(i, j), vi(i + 1, j), vi(i + 1, j + 1), vi(i, j + 1)], (0, 0, -1))
        # caras laterales donde la celda vecina no está cubierta
        vecinos = (((i, j - 1), (0, -1, 0), (i, j), (i + 1, j)),
                   ((i + 1, j), (1, 0, 0), (i + 1, j), (i + 1, j + 1)),
                   ((i, j + 1), (0, 1, 0), (i + 1, j + 1), (i, j + 1)),
                   ((i - 1, j), (-1, 0, 0), (i, j + 1), (i, j)))
        for (ni, nj), afuera, a, b in vecinos:
            if 0 <= ni < nx and 0 <= nj < ny and cub[(ni, nj)]:
                continue
            m.cara([vi(*a), vi(*b), vs(*b), vs(*a)], afuera)
    m.info = {"tipo": r.get("type"), "espesor": t}
    return m


def malla_losa(s, nombre="Losa"):
    """Sólido cerrado de una losa plana: todos sus rectángulos fundidos en uno.

    Una caja por rectángulo dejaba caras internas entre cajas vecinas, que coinciden
    con las caras de los muros que pasan por ese borde.
    """
    rects = [(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)) for x0, y0, x1, y1 in s["rects"]]
    xs, ys, cub = _grilla(rects)
    m = Malla(nombre)

    def vs(i, j):
        return m.v(xs[i], ys[j], s["z"])

    def vi(i, j):
        return m.v(xs[i], ys[j], s["z"] - s["t"])

    nx, ny = len(xs) - 1, len(ys) - 1
    for (i, j), ok in cub.items():
        if not ok:
            continue
        m.cara([vs(i, j), vs(i + 1, j), vs(i + 1, j + 1), vs(i, j + 1)], (0, 0, 1))
        m.cara([vi(i, j), vi(i + 1, j), vi(i + 1, j + 1), vi(i, j + 1)], (0, 0, -1))
        for (ni, nj), afuera, a, b in (((i, j - 1), (0, -1, 0), (i, j), (i + 1, j)),
                                       ((i + 1, j), (1, 0, 0), (i + 1, j), (i + 1, j + 1)),
                                       ((i, j + 1), (0, 1, 0), (i + 1, j + 1), (i, j + 1)),
                                       ((i - 1, j), (-1, 0, 0), (i, j + 1), (i, j))):
            if 0 <= ni < nx and 0 <= nj < ny and cub[(ni, nj)]:
                continue
            m.cara([vi(*a), vi(*b), vs(*b), vs(*a)], afuera)
    m.info = {"z": s["z"], "espesor": s["t"]}
    return m


# ------------------------------------------------------------------ muros

def poligono_muro(w):
    """Rectángulo en planta del muro según su alineación respecto del eje a-b."""
    (x1, y1), (x2, y2) = w["a"], w["b"]
    t = w["t"]
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < EPS:
        return None
    nx, ny = -dy / L, dx / L
    align = w.get("align", "center")
    if align == "center":
        o1, o2 = -t / 2.0, t / 2.0
    elif align == "left":
        o1, o2 = 0.0, t
    else:
        o1, o2 = -t, 0.0
    return [(x1 + nx * o1, y1 + ny * o1), (x2 + nx * o1, y2 + ny * o1),
            (x2 + nx * o2, y2 + ny * o2), (x1 + nx * o2, y1 + ny * o2)]


def _rect_muro(a, b, w):
    return poligono_muro({"a": a, "b": b, "t": w["t"], "align": w.get("align", "center")})


def _area_inter(p, q):
    """Área de intersección de dos rectángulos alineados a los ejes (o 0 si alguno no lo está)."""
    def caja(poly):
        xs = [v[0] for v in poly]
        ys = [v[1] for v in poly]
        if len({round(x, 6) for x in xs}) > 2 or len({round(y, 6) for y in ys}) > 2:
            return None
        return min(xs), min(ys), max(xs), max(ys)
    A, B = caja(p), caja(q)
    if A is None or B is None:
        return 0.0, None
    x0, y0 = max(A[0], B[0]), max(A[1], B[1])
    x1, y1 = min(A[2], B[2]), min(A[3], B[3])
    if x1 - x0 <= 1e-9 or y1 - y0 <= 1e-9:
        return 0.0, None
    return (x1 - x0) * (y1 - y0), (x0, y0, x1, y1)


def muros_ajustados(spec):
    """Eje (a, b) y coronación de cada muro, sin traslapes entre sólidos.

    1. Encuentros: si la zona común de dos muros del mismo nivel ocupa todo el
       espesor de uno de ellos en uno de sus extremos, ese muro se acorta hasta la
       cara del otro (en una esquina en L, el de índice mayor). Un cruce en medio de
       ambos muros no se toca.
    2. Losa encima: si la losa del nivel superior cubre el muro y su cara inferior
       queda bajo la coronación, el muro termina en la cara inferior de la losa.

    Devuelve [{"a", "b", "top", "recortes": [...], "bajo_losa": bool}] en el orden del JSON.
    """
    muros = spec["walls"]
    out = []
    for w in muros:
        out.append({"a": tuple(w["a"]), "b": tuple(w["b"]), "top": w["top"], "recortes": [],
                    "bajo_losa": False})
    for j, wj in enumerate(muros):
        aj, bj = out[j]["a"], out[j]["b"]
        L = math.hypot(bj[0] - aj[0], bj[1] - aj[1])
        if L < EPS:
            continue
        u = ((bj[0] - aj[0]) / L, (bj[1] - aj[1]) / L)
        for i, wi in enumerate(muros):
            if i == j or wi["level"] != wj["level"]:
                continue
            pj = _rect_muro(out[j]["a"], out[j]["b"], wj)
            pi = poligono_muro(wi)
            if not pj or not pi:
                continue
            area, inter = _area_inter(pj, pi)
            if area <= 1e-6:
                continue
            # largo de la zona común medido a lo largo de j, y si cubre todo su espesor
            x0, y0, x1, y1 = inter
            largo = (x1 - x0) if abs(u[0]) > 0.5 else (y1 - y0)
            ancho = (y1 - y0) if abs(u[0]) > 0.5 else (x1 - x0)
            if ancho < wj["t"] - 1e-6:
                continue
            a_cur, b_cur = out[j]["a"], out[j]["b"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            s_c = (cx - a_cur[0]) * u[0] + (cy - a_cur[1]) * u[1]
            Lc = math.hypot(b_cur[0] - a_cur[0], b_cur[1] - a_cur[1])
            en_inicio = s_c - largo / 2 <= 1e-6
            en_fin = s_c + largo / 2 >= Lc - 1e-6
            if not (en_inicio or en_fin):
                continue
            # ¿la zona común también está en un extremo de i? (esquina en L)
            ai, bi = tuple(wi["a"]), tuple(wi["b"])
            Li = math.hypot(bi[0] - ai[0], bi[1] - ai[1])
            ui = ((bi[0] - ai[0]) / Li, (bi[1] - ai[1]) / Li) if Li > EPS else (1, 0)
            s_i = (cx - ai[0]) * ui[0] + (cy - ai[1]) * ui[1]
            largo_i = (x1 - x0) if abs(ui[0]) > 0.5 else (y1 - y0)
            ancho_i = (y1 - y0) if abs(ui[0]) > 0.5 else (x1 - x0)
            extremo_i = s_i - largo_i / 2 <= 1e-6 or s_i + largo_i / 2 >= Li - 1e-6
            # en la L se acorta el de índice mayor, salvo que la zona común no cubra todo
            # su espesor: ese no se puede acortar y, si este tampoco se acorta, quedan
            # dos caras en el mismo plano (muro interior de 0,12 contra la esquina de uno de 0,20)
            if extremo_i and j < i and ancho_i >= wi["t"] - 1e-6:
                continue
            if largo >= Lc - 1e-6:
                continue                                   # no dejar el muro en cero
            if en_inicio:
                out[j]["a"] = (a_cur[0] + u[0] * largo, a_cur[1] + u[1] * largo)
            else:
                out[j]["b"] = (b_cur[0] - u[0] * largo, b_cur[1] - u[1] * largo)
            out[j]["recortes"].append({"contra": i, "largo": largo,
                                       "extremo": "inicio" if en_inicio else "fin"})
    niveles = {l["id"]: l["z"] for l in spec["levels"]}
    for j, w in enumerate(muros):
        z0 = niveles[w["level"]]
        poly = _rect_muro(out[j]["a"], out[j]["b"], w)
        if not poly:
            continue
        for s in spec.get("slabs", []):
            fondo = s["z"] - s["t"]
            if s["z"] <= z0 + 1e-6 or not (fondo < w["top"] - 1e-6):
                continue
            if all(en_rects(s["rects"], x, y) for x, y in poly) and fondo > z0 + 1e-6:
                out[j]["top"] = min(out[j]["top"], fondo)
                out[j]["bajo_losa"] = True
    return out


def poligonos_ajustados(spec):
    """[(muro con coronación ajustada, polígono ajustado)] en el orden del JSON."""
    out = []
    for w, a in zip(spec["walls"], muros_ajustados(spec)):
        out.append((dict(w, a=list(a["a"]), b=list(a["b"]), top=a["top"]),
                    _rect_muro(a["a"], a["b"], w)))
    return out


def en_poligono(poly, x, y):
    dentro = False
    n = len(poly)
    for i in range(n):
        (xa, ya), (xb, yb) = poly[i], poly[(i + 1) % n]
        if (ya > y) != (yb > y):
            xc = xa + (y - ya) * (xb - xa) / (yb - ya)
            if x < xc:
                dentro = not dentro
    return dentro


def _cortar_en_x(poly, xc):
    """Inserta vértices donde el contorno cruza la recta x = xc."""
    out = []
    n = len(poly)
    for i in range(n):
        (xa, ya), (xb, yb) = poly[i], poly[(i + 1) % n]
        out.append((xa, ya))
        if (xa - xc) * (xb - xc) < -1e-12:
            f = (xc - xa) / (xb - xa)
            out.append((xc, ya + f * (yb - ya)))
    return out


def _hastial_en_plano(spec, poly):
    """El JSON ya trae un hastial en el plano de este muro (no se duplica)."""
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    for gb in spec.get("gables", []):
        at = gb["at"]
        if gb.get("plane") == "y":
            if max(ys) - min(ys) < 0.5 and min(ys) - 0.05 <= at <= max(ys) + 0.05:
                return True
        elif max(xs) - min(xs) < 0.5 and min(xs) - 0.05 <= at <= max(xs) + 0.05:
            return True
    return False


def _losas_sobre(spec, z):
    return [rc for s in spec.get("slabs", []) if s["z"] > z + 1e-6 for rc in s["rects"]]


def muros_bajo_borde(spec):
    """Muros de fachada sobre los que pasa una cubierta dejando hueco.

    Un muro necesita cierre bajo la cubierta r cuando:
      - su centro está bajo r, y r es la cubierta más baja que pasa sobre él;
      - no tiene encima una losa ni un muro de un nivel superior;
      - de un lado hay cubierta o losa superior y del otro cielo abierto (es fachada);
      - la cara inferior de r queda sobre su coronación.
    El JSON trae los hastiales de los extremos; esos planos no se duplican.
    Devuelve [(indice_muro, indice_cubierta, poligono)].
    """
    niveles = {l["id"]: l["z"] for l in spec["levels"]}
    cubiertas = spec.get("roofs", [])
    todas = [rc for r in cubiertas for rc in rects_cubierta(r)]
    muros = poligonos_ajustados(spec)
    out = []
    for ir, r in enumerate(cubiertas):
        rects = rects_cubierta(r)
        t = espesor(r)
        for iw, (w, poly) in enumerate(muros):
            if not poly:
                continue
            z_nivel = niveles[w["level"]]
            cx = sum(p[0] for p in poly) / 4.0
            cy = sum(p[1] for p in poly) / 4.0
            if not en_rects(rects, cx, cy) or _hastial_en_plano(spec, poly):
                continue
            if any(r2 is not r and en_rects(rects_cubierta(r2), cx, cy)
                   and z_cubierta(r2, cx) < z_cubierta(r, cx) for r2 in cubiertas):
                continue
            sobre = _losas_sobre(spec, z_nivel)
            if en_rects(sobre, cx, cy, tol=-1e-6) or any(
                    niveles[w2["level"]] > z_nivel and p2 and en_poligono(p2, cx, cy)
                    for w2, p2 in muros):
                continue
            (x1, y1), (x2, y2) = w["a"], w["b"]
            L = math.hypot(x2 - x1, y2 - y1)
            nx, ny = -(y2 - y1) / L, (x2 - x1) / L
            d = w["t"] / 2.0 + 0.6
            lados = [en_rects(todas + sobre, cx + s * nx * d, cy + s * ny * d) for s in (1, -1)]
            if lados[0] == lados[1]:
                continue
            if max(z_cubierta(r, x) - t for x, _ in poly) <= w["top"] + 0.01:
                continue
            out.append((iw, ir, poly))
    return out


def _poligono_cierre(spec, ajuste, iw, con_cierre):
    """Planta del cierre sobre el muro iw: su eje ajustado, sin los recortes contra
    muros que no suben al espacio del cierre ni llevan cierre propio.

    Sobre la coronación de ese vecino no hay nada; si el cierre se acortara como el
    muro, quedaría una rendija entre el entretecho y el exterior.
    """
    a, b = ajuste[iw]["a"], ajuste[iw]["b"]
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    for rc in ajuste[iw]["recortes"]:
        k = rc["contra"]
        if k in con_cierre or ajuste[k]["top"] > ajuste[iw]["top"] + 1e-6:
            continue
        if rc["extremo"] == "inicio":
            a = (a[0] - u[0] * rc["largo"], a[1] - u[1] * rc["largo"])
        else:
            b = (b[0] + u[0] * rc["largo"], b[1] + u[1] * rc["largo"])
    return _rect_muro(a, b, spec["walls"][iw])


def cierres_bajo_cubierta(spec):
    """Sólidos que cierran el entretecho sobre los muros de `muros_bajo_borde`.

    Suben desde la coronación del muro hasta la cara INFERIOR de la cubierta cuando
    la cubierta cubre todo el muro (el cierre queda tapado por el faldón); si la
    banda no alcanza a cubrir el muro, hasta la cara superior, para no dejar rendija,
    y el caso se informa en `diagnostico`.
    """
    out = []
    ajustados = poligonos_ajustados(spec)
    ajuste = muros_ajustados(spec)
    bajo_borde = muros_bajo_borde(spec)
    con_cierre = {iw for iw, _, _ in bajo_borde}
    for iw, ir, _ in bajo_borde:
        w = ajustados[iw][0]
        poly = _poligono_cierre(spec, ajuste, iw, con_cierre)
        r = spec["roofs"][ir]
        t = espesor(r)
        rects = rects_cubierta(r)
        cubierto = all(en_rects(rects, x, y) for x, y in poly)
        bajo = t if cubierto else 0.0
        if r.get("type") == "gable":
            poly = _cortar_en_x(poly, r["ridge_x"])
        m = Malla("Cierre %s %02d" % (w["level"], iw + 1))

        def ztop(x):
            return max(z_cubierta(r, x) - bajo, w["top"] + 0.01)

        inf = [m.v(x, y, w["top"]) for x, y in poly]
        sup = [m.v(x, y, ztop(x)) for x, y in poly]
        m.cara(inf, (0, 0, -1))
        # la cara superior se parte en la cumbrera para que cada trozo sea plano
        if r.get("type") == "gable" and min(p[0] for p in poly) < r["ridge_x"] < max(p[0] for p in poly):
            for lado in (-1, 1):
                trozo = [k for k, p in enumerate(poly) if (p[0] - r["ridge_x"]) * lado >= -1e-9]
                m.cara([sup[k] for k in trozo], (0, 0, 1))
        else:
            m.cara(sup, (0, 0, 1))
        n = len(poly)
        cx = sum(p[0] for p in poly) / n
        cy = sum(p[1] for p in poly) / n
        for k in range(n):
            a, b = poly[k], poly[(k + 1) % n]
            mx, my = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy
            m.cara([inf[k], inf[(k + 1) % n], sup[(k + 1) % n], sup[k]], (mx, my, 0))
        m.info = {"muro": iw, "cubierta": ir, "hasta": "cara inferior" if cubierto else "cara superior"}
        out.append(m)
    return out


def atraviesan(spec, r):
    """Rectángulos de muros (alineados a los ejes) que atraviesan la cubierta r entera.

    Un muro atraviesa si arranca bajo la cara inferior del faldón y termina sobre su
    cara superior (con 5 cm de margen) en todo su ancho, y se cruza con las bandas.
    """
    t = espesor(r)
    rects = rects_cubierta(r)
    out = []
    niveles = {l["id"]: l["z"] for l in spec["levels"]}
    for w in spec["walls"]:
        poly = poligono_muro(w)
        if not poly:
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        if len({round(x, 6) for x in xs}) > 2 or len({round(y, 6) for y in ys}) > 2:
            continue                                     # muro oblicuo: no se recorta
        rc = (min(xs), min(ys), max(xs), max(ys))
        if not any(rc[0] < b[2] and b[0] < rc[2] and rc[1] < b[3] and b[1] < rc[3] for b in rects):
            continue
        base = niveles[w["level"]]
        zs = [z_cubierta(r, x) for x in (rc[0], rc[2])]
        if base <= min(zs) - t - 0.05 and w["top"] >= max(zs) + 0.05:
            out.append(rc)
    return out


def _recortar(poly, a, b):
    """Sutherland-Hodgman: parte del polígono (u, z) con z <= a*u + b."""
    out = []
    n = len(poly)
    for k in range(n):
        p, q = poly[k], poly[(k + 1) % n]
        fp = p[1] - (a * p[0] + b)
        fq = q[1] - (a * q[0] + b)
        if fp <= 1e-12:
            out.append(p)
        if (fp < -1e-12 < fq) or (fq < -1e-12 < fp):
            s = fp / (fp - fq)
            out.append((p[0] + s * (q[0] - p[0]), p[1] + s * (q[1] - p[1])))
    limpio = []
    for p in out:
        if not limpio or abs(p[0] - limpio[-1][0]) > 1e-9 or abs(p[1] - limpio[-1][1]) > 1e-9:
            limpio.append(p)
    if len(limpio) > 1 and abs(limpio[0][0] - limpio[-1][0]) < 1e-9 and abs(limpio[0][1] - limpio[-1][1]) < 1e-9:
        limpio.pop()
    return limpio


def hastiales(spec):
    """Hastiales del JSON, recortados bajo la cara INFERIOR de la cubierta que los tapa.

    El JSON los dibuja hasta la cara superior (convención de build3d.py): dentro de la
    cubierta su cara de arriba coincidía con la del faldón (parpadeo sobre el techo,
    franjas de 0,20 m en cada extremo). Si ninguna cubierta los tapa, quedan como vienen.
    """
    out = []
    for i, gb in enumerate(spec.get("gables", [])):
        perfil = [tuple(p) for p in gb.get("profile", [])]
        if len(perfil) < 3:
            continue
        en_y = gb.get("plane") == "y"
        at, t, d = gb["at"], gb.get("t", 0.2), gb.get("dir", 1)
        umid = sum(p[0] for p in perfil) / len(perfil)
        medio = at + d * t / 2.0

        def xy(u, eje):
            return (u, eje) if en_y else (eje, u)

        tapa = [r for r in spec.get("roofs", []) if en_rects(rects_cubierta(r), *xy(umid, medio))]
        if tapa:
            r = min(tapa, key=lambda r: z_cubierta(r, xy(umid, medio)[0]))
            tr = espesor(r)
            if en_y:
                # z_sup(x) es lineal por tramos en x = u: recorte por cada recta (región convexa)
                if r.get("type") == "gable":
                    a_, b_ = r["x_ref"]
                    rx, ez, rz = r["ridge_x"], r["eave_z"], r["ridge_z"]
                    rectas = [((rz - ez) / (rx - a_), ez - (rz - ez) / (rx - a_) * a_),
                              (-(rz - ez) / (b_ - rx), ez + (rz - ez) / (b_ - rx) * b_)]
                else:
                    (x0, z0), (x1, z1) = r["from"], r["to"]
                    pend = (z1 - z0) / (x1 - x0)
                    rectas = [(pend, z0 - pend * x0)]
            else:
                rectas = [(0.0, z_cubierta(r, at))]
            for a, b in rectas:
                perfil = _recortar(perfil, a, b - tr)
                if len(perfil) < 3:
                    break
        if len(perfil) < 3:
            continue
        m = Malla("Hastial %d" % (i + 1))
        e0, e1 = at, at + d * t
        cara0 = [m.v(*xy(u, e0), z) for u, z in perfil]
        cara1 = [m.v(*xy(u, e1), z) for u, z in perfil]
        n_eje = (0, -d, 0) if en_y else (-d, 0, 0)
        m.cara(cara0, n_eje)
        m.cara(cara1, tuple(-c for c in n_eje))
        cu = sum(p[0] for p in perfil) / len(perfil)
        cz = sum(p[1] for p in perfil) / len(perfil)
        k = len(perfil)
        for j in range(k):
            (u0, z0), (u1, z1) = perfil[j], perfil[(j + 1) % k]
            mu, mz = (u0 + u1) / 2 - cu, (z0 + z1) / 2 - cz
            afuera = (mu, 0, mz) if en_y else (0, mu, mz)
            m.cara([cara0[j], cara0[(j + 1) % k], cara1[(j + 1) % k], cara1[j]], afuera)
        m.info = {"hastial": i, "material": gb.get("material", "muro"), "recortado": bool(tapa)}
        out.append(m)
    return out


# ------------------------------------------------------------------ diagnóstico

def diagnostico(spec):
    """Sectores que los DATOS dejan sin cubrir. Lista de avisos (texto).

    - Losa sin nada encima (ni losa superior ni cubierta). Si el JSON deja un sector
      descubierto a propósito, eso no se puede saber desde aquí: se informa y decide
      quien proyecta.
    - Muro cuya coronación no tiene encima losa, muro superior ni cubierta entera:
      la banda de cubierta termina antes del muro y queda una rendija.
    """
    avisos = []
    cubiertas = spec.get("roofs", [])
    techos = [rc for r in cubiertas for rc in rects_cubierta(r)]
    niveles = {l["id"]: l["z"] for l in spec["levels"]}
    for s in spec.get("slabs", []):
        sobre = techos + _losas_sobre(spec, s["z"])
        xs, ys, cub = _grilla(s["rects"], extra=sobre)
        area = 0.0
        celdas = []
        for (i, j), ok in cub.items():
            if not ok:
                continue
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if not en_rects(sobre, cx, cy, tol=-1e-9):
                a = (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
                area += a
                celdas.append((xs[i], ys[j], xs[i + 1], ys[j + 1]))
        if area > 1e-6:
            avisos.append("losa z=%.2f: %.2f m2 sin nada encima, en %s"
                          % (s["z"], area, ", ".join("x %.2f-%.2f y %.2f-%.2f" % (c[0], c[2], c[1], c[3])
                                                      for c in celdas[:6])))
    muros = poligonos_ajustados(spec)
    for iw, (w, poly) in enumerate(muros):
        if not poly or _hastial_en_plano(spec, poly):
            continue
        z_nivel = niveles[w["level"]]
        cx = sum(p[0] for p in poly) / 4.0
        cy = sum(p[1] for p in poly) / 4.0
        tapado = en_rects(_losas_sobre(spec, z_nivel), cx, cy, tol=-1e-6) or any(
            niveles[w2["level"]] > z_nivel and p2 and en_poligono(p2, cx, cy) for w2, p2 in muros)
        if tapado:
            continue
        fuera = [p for p in poly if not en_rects(techos, *p)]
        if fuera:
            avisos.append("muro %d (%s %s->%s): su coronacion no queda entera bajo ninguna cubierta "
                          "(%s fuera): rendija entre muro y cubierta"
                          % (iw + 1, w["level"], spec["walls"][iw]["a"], spec["walls"][iw]["b"],
                             ", ".join("(%.2f, %.2f)" % p for p in fuera)))
    return avisos


def es_cerrada(m):
    """True si cada arista de la malla la comparten exactamente dos caras opuestas."""
    caras = m.caras if hasattr(m, "caras") else m["caras"]
    uso = {}
    for c in caras:
        n = len(c)
        for k in range(n):
            a, b = c[k], c[(k + 1) % n]
            uso[(a, b)] = uso.get((a, b), 0) + 1
    for (a, b), cnt in uso.items():
        if cnt != 1 or uso.get((b, a), 0) != 1:
            return False
    return True


def volumen(m):
    """Volumen con signo (positivo si las caras miran hacia afuera)."""
    verts = m.verts if hasattr(m, "verts") else m["verts"]
    caras = m.caras if hasattr(m, "caras") else m["caras"]
    v = 0.0
    for c in caras:
        p0 = verts[c[0]]
        for k in range(1, len(c) - 1):
            p1, p2 = verts[c[k]], verts[c[k + 1]]
            v += (p0[0] * (p1[1] * p2[2] - p1[2] * p2[1])
                  - p0[1] * (p1[0] * p2[2] - p1[2] * p2[0])
                  + p0[2] * (p1[0] * p2[1] - p1[1] * p2[0])) / 6.0
    return v


def generar(spec):
    """Todo lo que necesita un constructor: cubiertas, hastiales, cierres y avisos."""
    cub = [malla_cubierta(r, "Cubierta %d" % (i + 1), excluir=atraviesan(spec, r))
           for i, r in enumerate(spec.get("roofs", []))]
    return {"cubiertas": cub, "hastiales": hastiales(spec),
            "cierres": cierres_bajo_cubierta(spec), "avisos": diagnostico(spec)}
