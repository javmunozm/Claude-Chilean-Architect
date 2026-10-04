#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canales y bajadas de aguas lluvias, derivados de las cubiertas del JSON de planta.

Herramienta compartida (Python puro, como tools/cubierta.py): la usan los constructores
3D y el agente drainage-designer. Nada se dibuja a mano; todo sale de las cubiertas, los
muros y el terreno del JSON.

1. CANALES. Se recorre el borde de cada cubierta (unión de sus rectángulos) cada 5 cm:
   - ALERO: el agua escurre hacia afuera cruzando ese borde (la pendiente baja hacia él);
   - ENCUENTRO: el borde topa un muro más alto (canal adosado al muro, con forro y babeta);
   - nada: borde de testero o borde alto libre.
   Los tramos contiguos de la misma clase forman un canal.
2. ÁREA TRIBUTARIA. Para cada punto del canal se mide, aguas arriba y dentro de la
   cubierta, el largo hasta la cumbrera o el borde alto; área = suma de largos x paso
   (proyección horizontal). A un canal de encuentro se le suma una fracción del área
   del muro que lo domina (parámetro).
3. BAJADAS. Una en el extremo del canal más cercano a una esquina del edificio; dos (una
   por extremo) si el canal es más largo que el parámetro. Cada bajada baja por la cara
   del muro más próximo hasta el terreno (o el pavimento, si cae sobre uno).
4. VERIFICACIÓN. Q = C·i·A/3600 [L/s] por bajada contra su capacidad. Con la intensidad
   i en null (site.json) el resultado es INCONCLUSO, nunca CUMPLE; los parámetros con
   source UNVERIFIED tampoco permiten CUMPLE (mismo criterio que norm_check).

Coordenadas: las del JSON (x, y en m; z en m), igual que tools/cubierta.py.

    python tools/aguas_lluvias.py <planta.json> [--site site.json] [-o salida.json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cubierta  # noqa: E402

# shapely se importa dentro de las funciones que lo usan: mallas() corre también dentro
# de freecadcmd, cuyo Python puede no tener shapely.

PARAMS = json.loads((Path(__file__).resolve().parent / "norms" / "aguas_lluvias.json").read_text(encoding="utf-8"))
PASO = 0.05


def p(nombre):
    return PARAMS[nombre]["value"]


def _bajada_dir(r, x):
    """Sentido en x en que baja la cubierta r en la abscisa x (+1, -1 o 0 en la cumbrera)."""
    if r.get("type") == "gable":
        if abs(x - r["ridge_x"]) < 1e-6:
            return 0.0
        return -1.0 if x < r["ridge_x"] else 1.0
    (x0, z0), (x1, z1) = r["from"], r["to"]
    return math.copysign(1.0, (x1 - x0) * (z0 - z1)) if z0 != z1 else 0.0


def _muros(spec):
    from shapely.geometry import Point, Polygon, box  # noqa: F401
    from shapely.ops import unary_union  # noqa: F401
    out = []
    for w, poly in cubierta.poligonos_ajustados(spec):
        if poly:
            out.append((Polygon(poly), w["top"], w))
    return out


def _muro_mas_alto(muros, x, y, z):
    from shapely.geometry import Point, Polygon, box  # noqa: F401
    from shapely.ops import unary_union  # noqa: F401
    for pg, top, w in muros:
        if top > z + 0.10 and pg.buffer(0.02).contains(Point(x, y)):
            return pg, top, w
    return None


def _largo_aguas_arriba(r, union, x, y, sentido):
    """Largo horizontal desde (x, y) aguas arriba (contra 'sentido' en x) dentro de la cubierta."""
    from shapely.geometry import Point, Polygon, box  # noqa: F401
    from shapely.ops import unary_union  # noqa: F401
    largo, paso = 0.0, PASO
    xx = x - sentido * paso / 2
    while union.buffer(1e-6).contains(Point(xx, y)) and _bajada_dir(r, xx) == sentido:
        largo += paso
        xx -= sentido * paso
    return largo


def canales(spec):
    """Lista de canales: {tipo, cubierta, a, b, z, largo, area_m2, sentido_normal, ...}."""
    from shapely.geometry import Point, Polygon, box  # noqa: F401
    from shapely.ops import unary_union  # noqa: F401
    muros = _muros(spec)
    out = []
    for ir, r in enumerate(spec.get("roofs", [])):
        # simplify(0) quita los vértices alineados que dejan las bandas: un alero recto es
        # un solo canal aunque lo crucen varias bandas
        union = unary_union([box(*rc) for rc in cubierta.rects_cubierta(r)]).simplify(0)
        anillos = [union.exterior] + list(union.interiors) if union.geom_type == "Polygon" else \
            [g.exterior for g in union.geoms]
        for anillo in anillos:
            pts = list(anillo.coords)
            for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
                L = math.hypot(x1 - x0, y1 - y0)
                if L < 1e-6:
                    continue
                ux, uy = (x1 - x0) / L, (y1 - y0) / L
                nx, ny = uy, -ux                                   # normal: hacia afuera?
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                if union.contains(Point(mx + nx * 0.02, my + ny * 0.02)):
                    nx, ny = -nx, -ny
                muestras = []
                k = PASO / 2
                while k < L:
                    x, y = x0 + ux * k, y0 + uy * k
                    xi = x - nx * 0.01
                    z = cubierta.z_cubierta(r, xi)
                    s = _bajada_dir(r, xi)
                    clase = None
                    if abs(nx) > 0.5 and s * nx > 0:               # el agua cruza el borde
                        clase = "alero"
                    elif _muro_mas_alto(muros, x - nx * 0.1, y - ny * 0.1, z) or \
                            _muro_mas_alto(muros, x + nx * 0.1, y + ny * 0.1, z):
                        clase = "encuentro"
                    if clase == "alero":
                        area = _largo_aguas_arriba(r, union, xi, y, s) * PASO
                    else:
                        area = 0.0
                    muestras.append((k, clase, z, area))
                    k += PASO
                actual = None
                for k, clase, z, area in muestras + [(None, None, None, 0.0)]:
                    if actual and (clase != actual["tipo"] or k is None):
                        out.append(actual)
                        actual = None
                    if clase and actual is None:
                        actual = {"tipo": clase, "cubierta": ir, "k0": k, "k1": k, "z": [z, z],
                                  "area_m2": 0.0, "n": (nx, ny), "u": (ux, uy), "p0": (x0, y0)}
                    if clase and actual:
                        actual["k1"] = k
                        actual["z"][1] = z
                        actual["area_m2"] += area
    res = []
    for c in out:
        (x0, y0), (ux, uy) = c.pop("p0"), c.pop("u")
        k0, k1 = c.pop("k0") - PASO / 2, c.pop("k1") + PASO / 2
        c["a"] = (round(x0 + ux * k0, 3), round(y0 + uy * k0, 3))
        c["b"] = (round(x0 + ux * k1, 3), round(y0 + uy * k1, 3))
        c["largo"] = round(k1 - k0, 3)
        if c["largo"] < 0.3:
            continue
        if c["tipo"] == "encuentro":
            muro = _muro_mas_alto(muros, (c["a"][0] + c["b"][0]) / 2 - c["n"][0] * 0.1,
                                  (c["a"][1] + c["b"][1]) / 2 - c["n"][1] * 0.1, c["z"][0]) or \
                _muro_mas_alto(muros, (c["a"][0] + c["b"][0]) / 2 + c["n"][0] * 0.1,
                               (c["a"][1] + c["b"][1]) / 2 + c["n"][1] * 0.1, c["z"][0])
            alto = (muro[1] - c["z"][0]) if muro else 0.0
            c["area_muro_m2"] = round(alto * c["largo"], 3)
            # el muro puede atravesar la cubierta: el canal va contra su cara del lado de la
            # cubierta, no en el borde del rectángulo de cubierta (que queda dentro del muro)
            d = 0.0
            mx = (c["a"][0] + c["b"][0]) / 2
            my = (c["a"][1] + c["b"][1]) / 2
            while d < 1.0 and muro and muro[0].buffer(1e-6).contains(
                    Point(mx - c["n"][0] * (d + 0.005), my - c["n"][1] * (d + 0.005))):
                d += 0.005
            c["desfase_muro"] = round(d, 3)
            c["area_m2"] = c["area_muro_m2"] * p("fraccion_muro_vertical")
        c["area_m2"] = round(c["area_m2"], 3)
        c["z"] = round(min(c["z"]), 3)
        c["n"] = (round(c["n"][0], 3), round(c["n"][1], 3))
        res.append(c)
    return res


def _contorno(spec):
    from shapely.geometry import box
    from shapely.ops import unary_union
    return unary_union([box(*r) for s in spec.get("slabs", []) for r in s["rects"]])


def _esquinas(spec):
    u = _contorno(spec)
    geoms = getattr(u, "geoms", [u])
    return [c for g in geoms for c in g.exterior.coords]


def _suelo(spec, x, y):
    for pv in spec.get("paving", []):
        if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in pv["rects"]):
            return pv["z"]
    return spec.get("ground", {}).get("z", 0.0)


def bajadas(spec, cans):
    """Bajadas por canal: posición en el canal, punto en la cara del muro y cotas."""
    from shapely.geometry import Point, Polygon, box  # noqa: F401
    from shapely.ops import unary_union  # noqa: F401
    muros = _muros(spec)
    esq = _esquinas(spec)
    lado = p("bajada_lado_m")
    out = []
    contorno = _contorno(spec)
    for ic, c in enumerate(cans):
        if c["tipo"] == "encuentro":
            ux = (c["b"][0] - c["a"][0]) / c["largo"]
            uy = (c["b"][1] - c["a"][1]) / c["largo"]
            nx, ny = c["n"]
            off = c.get("desfase_muro", 0.0) + p("canal_ancho_m") / 2
            for q, sg in ((c["a"], -1), (c["b"], 1)):
                fuera = (q[0] + ux * sg * 0.1, q[1] + uy * sg * 0.1)
                if contorno.buffer(-1e-6).contains(Point(*fuera)):
                    continue                                  # ese extremo queda dentro
                gx, gy = q[0] - nx * off, q[1] - ny * off      # eje del canal en el extremo
                wx, wy = gx + ux * sg * (lado / 2 + 0.02), gy + uy * sg * (lado / 2 + 0.02)
                out.append({"canal": ic, "canal_xy": (round(gx, 3), round(gy, 3)),
                            "muro_xy": (round(wx, 3), round(wy, 3)),
                            "z_canal": round(c["z"] - espesor_canal(), 3),
                            "z_suelo": round(_suelo(spec, wx, wy), 3), "descarga": "a terreno"})
                break
            continue
        extremos = [c["a"], c["b"]]
        if c["largo"] <= p("largo_max_canal_por_bajada_m"):
            extremos = [min(extremos, key=lambda q: min(math.hypot(q[0] - e[0], q[1] - e[1]) for e in esq))]
        for q in extremos:
            # desde el extremo, avanzar a lo largo del canal hasta el primer punto con un muro
            # detrás (hacia adentro, contra la normal): la bajada baja por esa cara. En el
            # voladizo de un alero no hay muro y la bajada quedaría colgando.
            ux = (c["b"][0] - c["a"][0]) / c["largo"]
            uy = (c["b"][1] - c["a"][1]) / c["largo"]
            sg = 1 if q == c["a"] else -1
            nx, ny = c["n"]
            hallado = None
            t = lado / 2 + 0.05
            while t < c["largo"] - lado / 2 and hallado is None:
                gx, gy = q[0] + ux * sg * t, q[1] + uy * sg * t
                d = 0.0
                while d < 2.0:
                    xx, yy = gx - nx * d, gy - ny * d
                    # el muro debe subir hasta cerca del canal (no el del piso de abajo)
                    if any(pg.contains(Point(xx, yy)) and top >= c["z"] - 1.5 for pg, top, w in muros):
                        hallado = (gx, gy, d)
                        break
                    d += 0.01
                t += 0.05
            if hallado is None:
                gx, gy = q[0] + ux * sg * (lado / 2 + 0.05), q[1] + uy * sg * (lado / 2 + 0.05)
                wx, wy = gx, gy
            else:
                gx, gy, d = hallado
                # la bajada queda adosada a la cara del muro, a 15 cm de la esquina
                gx, gy = gx + ux * sg * 0.15, gy + uy * sg * 0.15
                wx, wy = gx - nx * (d - lado / 2 - 0.02), gy - ny * (d - lado / 2 - 0.02)
            # si bajo la bajada hay otra cubierta más baja, descarga sobre ella
            z_canal = c["z"] - espesor_canal()
            debajo = [cubierta.z_cubierta(r2, wx) for r2 in spec.get("roofs", [])
                      if cubierta.en_rects(cubierta.rects_cubierta(r2), wx, wy)
                      and cubierta.z_cubierta(r2, wx) < z_canal - 0.3]
            z_fin = max(debajo) if debajo else _suelo(spec, wx, wy)
            out.append({"canal": ic, "canal_xy": (round(gx, 3), round(gy, 3)),
                        "muro_xy": (round(wx, 3), round(wy, 3)),
                        "z_canal": round(z_canal, 3), "z_suelo": round(z_fin, 3),
                        "descarga": "sobre cubierta inferior" if debajo else "a terreno"})
    return out


def espesor_canal():
    return p("canal_alto_m")


def verificar(cans, bajs, site=None):
    """Caudal por bajada vs capacidad. INCONCLUSO sin intensidad o con parámetros UNVERIFIED."""
    i = (site or {}).get("rainfall_intensity_mm_h")
    C = p("coef_escorrentia_cubierta")
    cap = p("capacidad_bajada_l_s")
    no_verif = [k for k, v in PARAMS.items() if isinstance(v, dict) and v.get("source") == "UNVERIFIED"]
    filas = []
    for ic, c in enumerate(cans):
        nb = sum(1 for b in bajs if b["canal"] == ic)
        q = None if i is None else round(C * i * c["area_m2"] / 3600.0 / max(nb, 1), 3)
        if q is None:
            ver = "INCONCLUSO (falta rainfall_intensity_mm_h en site.json)"
        elif no_verif:
            ver = "INCONCLUSO (parámetros sin transcribir: %s)" % ", ".join(no_verif)
        else:
            ver = "CUMPLE" if q <= cap else "NO CUMPLE"
        filas.append({"canal": ic, "tipo": c["tipo"], "largo_m": c["largo"], "area_m2": c["area_m2"],
                      "bajadas": nb, "q_por_bajada_l_s": q, "veredicto": ver})
    return filas


def _caja(m, x0, y0, z0, x1, y1, z1):
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    v = [m.v(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    caras = [((0, 2, 3, 1), (0, 0, -1)), ((4, 5, 7, 6), (0, 0, 1)), ((0, 1, 5, 4), (0, -1, 0)),
             ((2, 6, 7, 3), (0, 1, 0)), ((0, 4, 6, 2), (-1, 0, 0)), ((1, 3, 7, 5), (1, 0, 0))]
    for idx, afuera in caras:
        m.cara([v[i] for i in idx], afuera)


def mallas(spec, cans=None, bajs=None):
    """Mallas cerradas (cubierta.Malla) de canales y bajadas, en coordenadas del JSON."""
    cans = canales(spec) if cans is None else cans
    bajs = bajadas(spec, cans) if bajs is None else bajs
    w, h, lado = p("canal_ancho_m"), p("canal_alto_m"), p("bajada_lado_m")
    out = []
    for ic, c in enumerate(cans):
        m = cubierta.Malla("Canal %02d (%s)" % (ic + 1, c["tipo"]))
        nx, ny = c["n"]
        (ax, ay), (bx, by) = c["a"], c["b"]
        # el canal queda por fuera del borde en un alero y por dentro (sobre la cubierta,
        # contra el muro) en un encuentro
        zt = c["z"] - 0.02
        if c["tipo"] == "alero":                      # por fuera del borde del alero
            d0, d1 = 0.0, w
        else:                                         # sobre la cubierta, contra la cara del muro
            d0, d1 = -(c.get("desfase_muro", 0.0) + 0.005), -(c.get("desfase_muro", 0.0) + 0.005 + w)
        xs = [ax + nx * d0, bx + nx * d0, ax + nx * d1, bx + nx * d1]
        ys = [ay + ny * d0, by + ny * d0, ay + ny * d1, by + ny * d1]
        _caja(m, min(xs), min(ys), zt - h, max(xs), max(ys), zt)
        m.info = {"tipo": "canal", "canal": ic}
        out.append(m)
    for ib, b in enumerate(bajs):
        m = cubierta.Malla("Bajada %02d" % (ib + 1))
        (gx, gy), (wx, wy) = b["canal_xy"], b["muro_xy"]
        zc, zs = b["z_canal"], b["z_suelo"]
        hl = lado / 2
        # tramo vertical por la cara del muro, desde el codo hasta el suelo
        _caja(m, wx - hl, wy - hl, zs, wx + hl, wy + hl, zc - 0.25)
        out.append(m)
        if math.hypot(gx - wx, gy - wy) > lado:
            m2 = cubierta.Malla("Bajada %02d codo" % (ib + 1))
            _caja(m2, min(gx, wx) - hl, min(gy, wy) - hl, zc - 0.25,
                  max(gx, wx) + hl, max(gy, wy) + hl, zc - 0.25 + lado)
            m2.info = {"tipo": "bajada", "bajada": ib}
            out.append(m2)
        m.info = {"tipo": "bajada", "bajada": ib}
    return out


def generar(spec, site=None):
    cans = canales(spec)
    bajs = bajadas(spec, cans)
    return {"canales": cans, "bajadas": bajs, "verificacion": verificar(cans, bajs, site),
            "parametros": {k: v for k, v in PARAMS.items() if k != "_meta"}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--site")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    site = json.loads(Path(a.site).read_text(encoding="utf-8")) if a.site else None
    res = generar(spec, site)
    for f in res["verificacion"]:
        c = res["canales"][f["canal"]]
        print("canal %02d %-9s largo %5.2f m  z %5.2f  área %6.2f m2  bajadas %d  %s"
              % (f["canal"] + 1, f["tipo"], f["largo_m"], c["z"], f["area_m2"], f["bajadas"], f["veredicto"]))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print("escrito", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
