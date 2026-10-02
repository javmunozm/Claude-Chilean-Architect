#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificación MEDIDA de un modelo 3D exportado a OBJ: techos, rendijas y superficies.

No mira cómo se construyó el modelo: triangula lo que hay en el OBJ y lanza rayos.
Sirve igual para el OBJ de FreeCAD (versions/vN/scripts/export_obj.py) y para el de Blender.

    python tools/scripts/verificar_modelo3d.py <modelo.obj> --spec <planta.json> \
        [--recintos <recintos.json>] [--desfase-y 14] [--y-directo]

Pruebas (cada una informa un número; ninguna se infiere):

  1. COBERTURA. Desde puntos de cada recinto interior (grilla de 0,25 m), un rayo
     vertical hacia arriba debe tocar algo (losa superior o cubierta). Un punto sin
     nada encima es un sector descubierto: se informa su superficie en m2.
  2. RENDIJAS. Desde esos mismos puntos, entre el dintel más alto del nivel y la
     cara inferior de lo que lo cubre, rayos horizontales en las 4 direcciones. Un
     rayo que recorre 40 m sin tocar nada salió al exterior por una abertura que
     no es un vano: una rendija entre muro y cubierta, o un faldón que no tapa.
  3. SUPERFICIES COINCIDENTES. Pares de triángulos coplanares que se superponen
     con la MISMA orientación: dos caras visibles en el mismo lugar, que en pantalla
     parpadean o se ven negras (z-fighting). Se informa el área superpuesta.
  4. CUBIERTA CERRADA. Las aristas de los triángulos del material "cubierta" deben
     compartirse de a dos: si no, la cubierta tiene bordes abiertos o caras internas.

El OBJ debe venir TRIANGULADO (FreeCAD v2 ya lo escribe así; desde Blender exportar
con export_triangulated_mesh=True): un polígono cóncavo abierto en abanico produce
triángulos que se superponen y que la prueba 3 contaría como superficies duplicadas.

Coordenadas: el OBJ usa Y arriba, (x, z, -y). y_planta = desfase - z_obj:
  FreeCAD v2 (export_obj.py, origen esquina NO)  -> --desfase-y 14
  Blender (wm.obj_export por defecto)            -> --desfase-y 0
  tools/scripts/build3d.py escribe (x, z, y) sin rotar -> --y-directo (y_planta = z_obj)

Sale con código 1 si hay sectores descubiertos o rendijas.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict

import numpy as np

try:
    from shapely.geometry import Point, Polygon, box
    from shapely.ops import unary_union
except ImportError:
    print("error: falta shapely", file=sys.stderr)
    raise SystemExit(2)

PASO_GRILLA = 0.25
PASO_ALTURA = 0.20
ESCAPE = 40.0
EPS = 1e-9


# ------------------------------------------------------------------ lectura OBJ

def leer_obj(path, desfase_y, y_directo=False):
    """Triángulos (N,3,3) en coordenadas de planta (x, y, z) y su material."""
    verts, tris, mats = [], [], []
    mat = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if ln.startswith("v "):
                _, a, b, c = ln.split()[:4]
                x, yup, zo = float(a), float(b), float(c)
                verts.append((x, desfase_y + zo if y_directo else desfase_y - zo, yup))
            elif ln.startswith("usemtl"):
                mat = ln.split(None, 1)[1].strip()
            elif ln.startswith("f "):
                idx = [int(p.split("/")[0]) for p in ln.split()[1:]]
                idx = [i - 1 if i > 0 else len(verts) + i for i in idx]
                for k in range(1, len(idx) - 1):          # abanico
                    tris.append((idx[0], idx[k], idx[k + 1]))
                    mats.append(mat or "")
    V = np.array(verts, dtype=float)
    T = V[np.array(tris, dtype=int)]
    return T, np.array(mats)


# ------------------------------------------------------------------ rayos

class Trazador:
    def __init__(self, T):
        self.v0 = T[:, 0]
        self.e1 = T[:, 1] - T[:, 0]
        self.e2 = T[:, 2] - T[:, 0]
        lo = T.min(axis=1)
        hi = T.max(axis=1)
        self.lo, self.hi = lo, hi

    def primer_impacto(self, o, d, tmax=ESCAPE):
        """Distancia al primer triángulo en la dirección d (Möller-Trumbore), o None."""
        o = np.asarray(o, float)
        d = np.asarray(d, float)
        # descarte por caja: solo triángulos cuya caja cruza el segmento
        seg_lo = np.minimum(o, o + d * tmax) - 1e-6
        seg_hi = np.maximum(o, o + d * tmax) + 1e-6
        m = np.all((self.hi >= seg_lo) & (self.lo <= seg_hi), axis=1)
        if not m.any():
            return None
        v0, e1, e2 = self.v0[m], self.e1[m], self.e2[m]
        p = np.cross(d, e2)
        det = np.einsum("ij,ij->i", e1, p)
        ok = np.abs(det) > EPS
        inv = np.zeros_like(det)
        inv[ok] = 1.0 / det[ok]
        s = o - v0
        u = np.einsum("ij,ij->i", s, p) * inv
        q = np.cross(s, e1)
        v = (q @ d) * inv
        t = np.einsum("ij,ij->i", e2, q) * inv
        hit = ok & (u >= -1e-7) & (v >= -1e-7) & (u + v <= 1 + 1e-7) & (t > 1e-6) & (t < tmax)
        if not hit.any():
            return None
        return float(t[hit].min())


# ------------------------------------------------------------------ zonas de prueba

def zonas_interiores(spec, recintos):
    """Polígonos interiores por nivel: recintos no exteriores, o la losa si no hay recintos."""
    out = {}
    niveles = {l["id"]: l["z"] for l in spec["levels"]}
    for lv, z in niveles.items():
        polys = []
        if recintos and lv in recintos.get("niveles", {}):
            for r in recintos["niveles"][lv]["recintos"]:
                pts = r.get("neto") or r.get("bruto")
                if not pts or r.get("tipo") == "exterior":
                    continue
                polys.append((r.get("label") or r.get("nombre"), Polygon(pts)))
        else:
            rects = [box(*rc) for s in spec.get("slabs", []) if abs(s["z"] - z) < 1e-6
                     for rc in s["rects"]]
            if rects:
                polys.append(("losa %s" % lv, unary_union(rects)))
        out[lv] = polys
    return out


def puntos(poly, paso=PASO_GRILLA, margen=0.12):
    pg = poly.buffer(-margen)
    if pg.is_empty:
        return []
    x0, y0, x1, y1 = pg.bounds
    pts = []
    x = x0 + paso / 2
    while x < x1:
        y = y0 + paso / 2
        while y < y1:
            if pg.contains(Point(x, y)):
                pts.append((x, y))
            y += paso
        x += paso
    return pts


# ------------------------------------------------------------------ superficies

def superficies_coincidentes(T, mats):
    """Área de superposición entre triángulos coplanares con igual orientación."""
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    a = np.linalg.norm(n, axis=1)
    ok = a > 1e-10
    n[ok] = n[ok] / a[ok, None]
    planos = defaultdict(list)
    for i in np.nonzero(ok)[0]:
        nn = n[i]
        d = float(nn @ T[i, 0])
        clave = (round(nn[0], 3), round(nn[1], 3), round(nn[2], 3), round(d, 3))
        planos[clave].append(i)
    total = 0.0
    pares = 0
    ejemplos = []
    por_par = defaultdict(float)
    for clave, idx in planos.items():
        if len(idx) < 2:
            continue
        nn = np.array(clave[:3])
        # proyección 2D sobre el plano
        ax = int(np.argmax(np.abs(nn)))
        keep = [k for k in range(3) if k != ax]
        polys = [Polygon(T[i][:, keep]) for i in idx]
        for j in range(len(idx)):
            pj = polys[j]
            if pj.area < 1e-8:
                continue
            for k in range(j + 1, len(idx)):
                pk = polys[k]
                if not pj.intersects(pk):
                    continue
                inter = pj.intersection(pk).area
                if inter > 1e-4:
                    # el área proyectada se corrige por la inclinación del plano
                    area = inter / max(abs(nn[ax]), 1e-6)
                    total += area
                    pares += 1
                    por_par[" / ".join(sorted((mats[idx[j]], mats[idx[k]])))] += area
                    if len(ejemplos) < 8:
                        c = T[idx[j]].mean(axis=0)
                        ejemplos.append((round(area, 3), mats[idx[j]], mats[idx[k]],
                                         tuple(round(float(v), 2) for v in c)))
    return total, pares, ejemplos, dict(por_par)


def aristas_abiertas(T, mats, material="cubierta"):
    sel = T[mats == material]
    if len(sel) == 0:
        return None
    clave = lambda p: (round(p[0], 4), round(p[1], 4), round(p[2], 4))  # noqa: E731
    uso = defaultdict(int)
    for t in sel:
        ks = [clave(p) for p in t]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            uso[frozenset((ks[a], ks[b]))] += 1
    impares = sum(1 for c in uso.values() if c != 2)
    return impares, len(uso)


# ------------------------------------------------------------------ principal

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("obj")
    ap.add_argument("--spec", required=True, help="JSON de planta (niveles, losas, vanos)")
    ap.add_argument("--recintos", help="JSON con polígonos de recinto (neto/bruto, tipo)")
    ap.add_argument("--desfase-y", type=float, default=0.0)
    ap.add_argument("--y-directo", action="store_true",
                    help="OBJ de build3d.py: (x, altura, y) sin rotar, y_planta = z_obj")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    spec = json.load(open(args.spec, encoding="utf-8"))
    recintos = json.load(open(args.recintos, encoding="utf-8")) if args.recintos else None
    T, mats = leer_obj(args.obj, args.desfase_y, args.y_directo)
    tr = Trazador(T)
    niveles = {l["id"]: l["z"] for l in spec["levels"]}
    dintel = defaultdict(float)
    for o in spec.get("openings", []):
        dintel[o["level"]] = max(dintel[o["level"]], o.get("head", 0.0) or 0.0)

    informe = {"obj": args.obj, "triangulos": int(len(T)), "niveles": {}}
    descubierto_total = 0.0
    rendijas_total = 0
    for lv, zonas in zonas_interiores(spec, recintos).items():
        z0 = niveles[lv]
        cel = PASO_GRILLA ** 2
        res = {"descubierto_m2": 0.0, "rendijas": 0, "rayos": 0, "detalle": []}
        for nombre, pg in zonas:
            sin_techo = 0
            fugas = []
            for (x, y) in puntos(pg):
                arriba = tr.primer_impacto((x, y, z0 + 0.05), (0, 0, 1))
                if arriba is None:
                    sin_techo += 1
                    continue
                z_cielo = z0 + 0.05 + arriba
                z = z0 + dintel[lv] + 0.08
                while z < z_cielo - 0.05:
                    for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)):
                        res["rayos"] += 1
                        if tr.primer_impacto((x, y, z), d) is None:
                            fugas.append((round(x, 2), round(y, 2), round(z, 2), d))
                    z += PASO_ALTURA
            if sin_techo or fugas:
                res["detalle"].append({
                    "zona": nombre, "descubierto_m2": round(sin_techo * cel, 2),
                    "rayos_que_escapan": len(fugas), "ejemplos": fugas[:4]})
            res["descubierto_m2"] += sin_techo * cel
            res["rendijas"] += len(fugas)
        res["descubierto_m2"] = round(res["descubierto_m2"], 2)
        descubierto_total += res["descubierto_m2"]
        rendijas_total += res["rendijas"]
        informe["niveles"][lv] = res

    area_zf, pares_zf, ej_zf, par_zf = superficies_coincidentes(T, mats)
    informe["superficies_coincidentes"] = {"area_m2": round(area_zf, 3), "pares": pares_zf,
                                          "por_material": {k: round(v, 3) for k, v in par_zf.items()},
                                          "ejemplos": ej_zf}
    ab = aristas_abiertas(T, mats)
    informe["cubierta_aristas_no_pareadas"] = None if ab is None else {"no_pareadas": ab[0],
                                                                       "aristas": ab[1]}

    if args.as_json:
        print(json.dumps(informe, indent=1, ensure_ascii=False))
    else:
        print("Verificación 3D - %s  (%d triángulos)" % (args.obj, len(T)))
        print("=" * 78)
        for lv, r in informe["niveles"].items():
            print("[%s] sin techo: %.2f m2   rayos que escapan: %d de %d"
                  % (lv, r["descubierto_m2"], r["rendijas"], r["rayos"]))
            for d in r["detalle"]:
                print("      %-28s sin techo %.2f m2, escapan %d  ej. %s"
                      % (d["zona"], d["descubierto_m2"], d["rayos_que_escapan"], d["ejemplos"][:2]))
        print("superficies coincidentes visibles: %.3f m2 en %d pares" % (area_zf, pares_zf))
        for k, v in sorted(par_zf.items(), key=lambda kv: -kv[1]):
            print("      %-24s %.3f m2" % (k, v))
        if ab is not None:
            print("cubierta: %d aristas no pareadas de %d" % ab)
        print("-" * 78)
        ok = descubierto_total == 0 and rendijas_total == 0
        print("RESULTADO:", "OK - todo cubierto y sin rendijas" if ok else
              "FALLA - %.2f m2 sin techo, %d rayos escapan" % (descubierto_total, rendijas_total))
    return 0 if (descubierto_total == 0 and rendijas_total == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
