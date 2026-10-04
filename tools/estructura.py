#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Predimensionamiento estructural de una vivienda de muros: cargas, sismo estático,
densidad y corte de muros, viga, voladizo y cimientos.

Herramienta compartida del agente structural-calculator. Lee:
  - el JSON de planta (muros, vanos, losas, cubiertas; coordenadas del JSON),
  - el model_extract.json MEDIDO del modelo (volúmenes de muros, losas),
  - el site.json (zona sísmica y suelo; null = escenarios),
  - la propuesta estructural de la versión (source/estructura.json),
  - los parámetros de tools/norms/estructura.json.

Qué NO es: el proyecto de cálculo estructural que exige el permiso de edificación. Eso
lo firma un ingeniero civil. Esto es un predimensionamiento para anteproyecto que deja
los números a la vista, con cada parámetro marcado según su fuente. Mientras haya
parámetros UNVERIFIED o datos del sitio en null, todo veredicto es INCONCLUSO (mismo
criterio que tools/norm_check.py).

    python tools/estructura.py <planta.json> --extract <model_extract.json> \
        --site <site.json> --propuesta <estructura.json> [--recintos <recintos.json>] \
        [-o estructura_calc.json] [--memoria memoria.md]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cubierta  # noqa: E402

from shapely.geometry import LineString, Point, Polygon, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

PAR = json.loads((Path(__file__).resolve().parent / "norms" / "estructura.json").read_text(encoding="utf-8"))


def v(grupo, nombre):
    return PAR[grupo][nombre]["value"]


def no_verificados():
    out = []
    for g, d in PAR.items():
        if g.startswith("_"):
            continue
        for k, x in d.items():
            if isinstance(x, dict) and x.get("source") == "UNVERIFIED":
                out.append("%s.%s" % (g, k))
    return out


# ------------------------------------------------------------------ muros

def muros(spec, t_min):
    """Muros por nivel con su largo neto (descontados los vanos) y dirección."""
    vanos = spec.get("openings", [])
    out = []
    for (w, poly), aj in zip(cubierta.poligonos_ajustados(spec), cubierta.muros_ajustados(spec)):
        if not poly:
            continue
        (ax, ay), (bx, by) = aj["a"], aj["b"]
        L = math.hypot(bx - ax, by - ay)
        dirx = abs(bx - ax) >= abs(by - ay)
        pg = Polygon(poly)
        hueco = 0.0
        for o in vanos:
            if o["level"] != w["level"]:
                continue
            x0, y0, x1, y1 = o["rect"]
            if pg.buffer(0.03).contains(Point((x0 + x1) / 2, (y0 + y1) / 2)):
                hueco += (x1 - x0) if dirx else (y1 - y0)
        out.append({"nivel": w["level"], "t": w["t"], "dir": "X" if dirx else "Y", "largo": round(L, 3),
                    "largo_neto": round(max(L - hueco, 0.0), 3), "estructural": w["t"] >= t_min - 1e-6,
                    "poly": pg, "a": (ax, ay), "b": (bx, by), "top": aj["top"]})
    return out


def pesos(extract, spec, t_min):
    """Pesos (kN) por grupo, desde los volúmenes MEDIDOS del modelo."""
    g_alb = v("pesos", "albanileria_kN_m3")
    g_ha = v("pesos", "hormigon_armado_kN_m3")
    q_tab = v("pesos", "tabique_liviano_kN_m2")
    P = {"muros_p1": 0.0, "muros_p2": 0.0, "tabiques_p1": 0.0, "tabiques_p2": 0.0, "hastiales_cierres": 0.0}
    for e in extract["entities"]:
        if e["kind"] != "wall":
            continue
        nombre = e["name"]
        if nombre.startswith("Muro p1") or nombre.startswith("Muro p2"):
            lv = "p1" if nombre.startswith("Muro p1") else "p2"
            if (e.get("thickness") or 0) >= t_min - 1e-6:
                P["muros_" + lv] += e["volume"] * g_alb
            else:
                P["tabiques_" + lv] += (e.get("length") or 0) * (e.get("height") or 0) * q_tab
        else:
            P["hastiales_cierres"] += e["volume"] * g_alb
    losa = next(e for e in extract["entities"] if e["kind"] == "slab" and e.get("level_z", 0) > 0.1)
    P["losa_p2"] = losa["volume"] * g_ha
    P["terminaciones_p2"] = losa["area"] * v("pesos", "terminaciones_piso_kN_m2")
    area_cub = sum(unary_union([box(*rc) for rc in cubierta.rects_cubierta(r)]).area for r in spec.get("roofs", []))
    P["cubierta"] = area_cub * v("pesos", "cubierta_kN_m2")
    L = {"vivienda_p2": losa["area"] * v("sobrecargas", "vivienda_kN_m2"),
         "cubierta": area_cub * v("sobrecargas", "cubierta_kN_m2")}
    return ({k: round(x, 1) for k, x in P.items()}, {k: round(x, 1) for k, x in L.items()},
            round(losa["area"], 2), round(area_cub, 2))


# ------------------------------------------------------------------ sismo

def sismo(P, L, z_p2, z_techo, site):
    fr = v("sobrecargas", "fraccion_sismica_vivienda")
    P_p2 = P["losa_p2"] + P["terminaciones_p2"] + fr * L["vivienda_p2"] + \
        0.5 * (P["muros_p1"] + P["tabiques_p1"] + P["muros_p2"] + P["tabiques_p2"])
    P_te = P["cubierta"] + P["hastiales_cierres"] + 0.5 * (P["muros_p2"] + P["tabiques_p2"])
    Ptot = P_p2 + P_te
    H = z_techo

    def A(zk_1, zk):
        return math.sqrt(1 - zk_1 / H) - math.sqrt(1 - zk / H)
    A1, A2 = A(0.0, z_p2), A(z_p2, H)
    escenarios = []
    for zona, a0 in v("sismo", "A0_g_por_zona").items():
        for suelo, S in v("sismo", "S_por_suelo").items():
            C = max(v("sismo", "Cmax_factor_R4") * S * a0, a0 * S / v("sismo", "Cmin_divisor"))
            Q0 = C * v("sismo", "I_vivienda") * Ptot
            F2 = A2 * P_te / (A1 * P_p2 + A2 * P_te) * Q0
            escenarios.append({"zona": zona, "suelo": suelo, "C": round(C, 4), "Q0_kN": round(Q0, 1),
                               "corte_p2_kN": round(F2, 1), "corte_p1_kN": round(Q0, 1)})
    zona, suelo = (site or {}).get("seismic", {}).get("zone"), (site or {}).get("seismic", {}).get("soil_type")
    del_sitio = next((e for e in escenarios if e["zona"] == str(zona) and e["suelo"] == suelo), None)
    peor = max(escenarios, key=lambda e: e["Q0_kN"])
    return {"P_nivel_p2_kN": round(P_p2, 1), "P_nivel_techo_kN": round(P_te, 1), "P_total_kN": round(Ptot, 1),
            "z_p2": z_p2, "z_techo": z_techo, "escenarios": escenarios, "del_sitio": del_sitio,
            "peor": peor, "zona_sitio": zona, "suelo_sitio": suelo}


def corte_muros(ms, P, sis, areas_piso):
    """Densidad y capacidad al corte de los muros estructurales por nivel y dirección."""
    a, b = v("albanileria", "corte_admisible")["a"], v("albanileria", "corte_admisible")["b"]
    tau = v("albanileria", "tau_m_MPa") * 1000.0
    out = []
    carga_sobre = {"p1": sis["P_total_kN"], "p2": sis["P_nivel_techo_kN"]}
    caso = sis["del_sitio"] or sis["peor"]
    for lv in ("p1", "p2"):
        est = [m for m in ms if m["nivel"] == lv and m["estructural"]]
        A_tot = sum(m["largo_neto"] * m["t"] for m in est)
        sigma0 = carga_sobre[lv] / A_tot if A_tot else 0.0
        Q = caso["corte_%s_kN" % lv]
        for d in ("X", "Y"):
            Ad = sum(m["largo_neto"] * m["t"] for m in est if m["dir"] == d)
            Va = (a * tau + b * sigma0) * Ad
            out.append({"nivel": lv, "dir": d, "largo_neto_m": round(sum(m["largo_neto"] for m in est if m["dir"] == d), 2),
                        "area_muros_m2": round(Ad, 3), "area_piso_m2": areas_piso[lv],
                        "densidad_pct": round(100 * Ad / areas_piso[lv], 2) if areas_piso[lv] else None,
                        "sigma0_kPa": round(sigma0, 1), "Va_kN": round(Va, 1), "Q_kN": Q,
                        "uso": round(Q / Va, 3) if Va else None})
    return out, caso


# ------------------------------------------------------------------ elementos

def viga(ms, prop, P_par):
    vg = prop["viga_eje_B"]
    x, y0, y1, Lv = vg["x"], vg["y0"], vg["y1"], vg["luz_m"]
    linea = LineString([(x, y0), (x, y1)])
    g_alb = v("pesos", "albanileria_kN_m3")
    w_muro = 0.0
    for m in ms:
        if m["nivel"] == "p2" and m["poly"].buffer(0.05).intersects(linea):
            sobre = m["poly"].intersection(linea.buffer(0.15)).area / max(m["t"], 1e-6)
            alto = m["top"] - 2.85
            # envolvente: se pesa como albañilería aunque la propuesta lo declare tabique liviano
            w_muro += m["t"] * alto * g_alb * min(sobre, Lv) / Lv
    # ancho tributario de losa: mitad de la distancia a los muros p1 paralelos más cercanos
    izq, der = -1e9, 1e9
    for m in ms:
        if m["nivel"] != "p1" or not m["estructural"] or m["dir"] != "Y":
            continue
        ys = sorted([m["a"][1], m["b"][1]])
        if min(ys[1], y1) - max(ys[0], y0) < 0.5 * Lv:
            continue
        xm = (m["a"][0] + m["b"][0]) / 2
        if xm < x - 0.3:
            izq = max(izq, xm)
        elif xm > x + 0.3:
            der = min(der, xm)
    trib = ((x - izq) if izq > -1e8 else 0.0) / 2 + ((der - x) if der < 1e8 else 0.0) / 2
    h = Lv / v("predimension", "viga_L_sobre_h")
    b = 0.20
    e_losa = prop["losa_p2"]["espesor_m"]
    pp = b * max(h - e_losa, 0.0) * v("pesos", "hormigon_armado_kN_m3")  # descolgado bajo la losa
    D = w_muro + pp + trib * (e_losa * v("pesos", "hormigon_armado_kN_m3") + v("pesos", "terminaciones_piso_kN_m2"))
    L = trib * v("sobrecargas", "vivienda_kN_m2")
    k = v("hormigon", "combinacion_ultima")
    wu = k["D"] * D + k["L"] * L
    M, V = wu * Lv ** 2 / 8, wu * Lv / 2
    d = h - v("hormigon", "recubrimiento_util_m")
    As = M / (v("hormigon", "phi_flexion") * 0.9 * d * v("hormigon", "fy_MPa") * 1000) * 1e4
    return {"luz_m": Lv, "muro_sobre_kN_m": round(w_muro, 2), "ancho_tributario_m": round(trib, 2),
            "D_kN_m": round(D, 2), "L_kN_m": round(L, 2), "wu_kN_m": round(wu, 2), "Mu_kNm": round(M, 1),
            "Vu_kN": round(V, 1), "h_predim_m": round(h, 2), "b_m": b, "peso_propio_kN_m": round(pp, 2), "As_cm2": round(As, 2),
            "nota": "muro del 2º piso sobre la viga (pesado como albañilería: envolvente, la propuesta lo declara tabique de 12 cm) + peso propio del descolgado + losa tributaria; la cubierta que pueda cargar ese muro no se incluyó"}


def voladizo(prop):
    Lc = prop["voladizo_patio"]["luz_m"]
    e = prop["losa_p2"]["espesor_m"]
    D = e * v("pesos", "hormigon_armado_kN_m3") + v("pesos", "terminaciones_piso_kN_m2")
    L = v("sobrecargas", "vivienda_kN_m2")
    k = v("hormigon", "combinacion_ultima")
    wu = k["D"] * D + k["L"] * L
    M = wu * Lc ** 2 / 2
    d = e - v("hormigon", "recubrimiento_util_m")
    As = M / (v("hormigon", "phi_flexion") * 0.9 * d * v("hormigon", "fy_MPa") * 1000) * 1e4
    h_min = Lc / v("predimension", "voladizo_L_sobre_h")
    return {"luz_m": Lc, "espesor_m": e, "h_min_m": round(h_min, 3), "wu_kN_m2": round(wu, 2),
            "Mu_kNm_por_m": round(M, 2), "As_cm2_por_m": round(As, 2), "espesor_suficiente": e >= h_min}


def losa_luces(spec, recintos):
    """Luz mayor de losa del 2º piso: el lado menor del recinto más grande del p1 bajo ella."""
    if not recintos:
        return None
    losa = next(s for s in spec["slabs"] if s["z"] > 0.1)
    techo = unary_union([box(*r) for r in losa["rects"]])
    mayor = None
    for r in recintos["niveles"]["p1"]["recintos"]:
        if r.get("tipo") == "exterior" or "neto" not in r:
            continue
        pg = Polygon(r["neto"])
        if not techo.contains(pg.centroid):
            continue
        x0, y0, x1, y1 = pg.bounds
        luz = min(x1 - x0, y1 - y0)
        if mayor is None or luz > mayor[1]:
            mayor = (r["label"], luz)
    e = losa["t"]
    hmin = mayor[1] / v("predimension", "losa_L_sobre_h_continua")
    return {"recinto": mayor[0], "luz_m": round(mayor[1], 2), "espesor_m": e, "h_min_m": round(hmin, 3),
            "espesor_suficiente": e >= hmin}


def cimientos(ms, P, sis):
    """Carga lineal de servicio sobre el cimiento y ancho para cada escenario de suelo."""
    est_p1 = [m for m in ms if m["nivel"] == "p1" and m["estructural"]]
    L_p1 = sum(m["largo"] for m in est_p1)
    q_media = sis["P_total_kN"] / L_p1 if L_p1 else 0.0
    # el muro más cargado: p1 con muro p2 encima en su misma línea
    q_max = q_media
    g = v("pesos", "albanileria_kN_m3")
    for m in est_p1:
        sobre = [n for n in ms if n["nivel"] == "p2" and n["estructural"] and n["poly"].buffer(0.05).intersects(m["poly"])]
        if sobre:
            extra = sum(n["t"] * (n["top"] - 2.85) * g for n in sobre[:1])
            q_max = max(q_max, q_media + extra)
    out = []
    for s in v("suelo", "escenarios_sigma_adm_kPa"):
        out.append({"sigma_adm_kPa": s, "b_media_m": round(q_media / s, 2), "b_max_m": round(q_max / s, 2)})
    return {"largo_muros_p1_m": round(L_p1, 2), "q_media_kN_m": round(q_media, 1),
            "q_max_kN_m": round(q_max, 1), "escenarios": out}


# ------------------------------------------------------------------ todo

def calcular(spec, extract, site, prop, recintos=None):
    t_min = prop.get("muros_estructurales_espesor_min_m", 0.20)
    ms = muros(spec, t_min)
    P, L, area_p2, area_cub = pesos(extract, spec, t_min)
    lv = {l["id"]: l["z"] for l in spec["levels"]}
    z_techo = max(w["top"] for w in spec["walls"] if w["level"] == "p2")
    sis = sismo(P, L, lv["p2"], z_techo, site)
    areas_piso = {"p1": next(e["area"] for e in extract["entities"] if e["kind"] == "slab" and e.get("level_z", 1) < 0.1),
                  "p2": area_p2}
    cm, caso = corte_muros(ms, P, sis, areas_piso)
    nv = no_verificados()
    sitio_ok = sis["del_sitio"] is not None
    if not sitio_ok:
        veredicto = "INCONCLUSO: zona sísmica y suelo del sitio en null (site.json); se muestran escenarios y el más desfavorable"
    elif nv:
        veredicto = "INCONCLUSO: %d parámetros sin transcribir de su norma" % len(nv)
    else:
        veredicto = "verificable"
    return {"_nota": "Predimensionamiento (tools/estructura.py). No reemplaza el proyecto de cálculo firmado por un ingeniero civil.",
            "veredicto": veredicto, "parametros_no_verificados": nv, "propuesta": prop,
            "pesos_kN": P, "sobrecargas_kN": L, "area_losa_p2_m2": area_p2, "area_cubiertas_m2": area_cub,
            "sismo": sis, "caso_corte": caso, "muros": cm,
            "viga_eje_B": viga(ms, prop, P), "voladizo_patio": voladizo(prop),
            "losa_p2": losa_luces(spec, recintos), "cimientos": cimientos(ms, P, sis)}


def f(x, d=2):
    return ("%%.%df" % d % x).replace(".", ",")


def memoria_md(res, titulo):
    """Memoria de cálculo (predimensionamiento) en Markdown, con todos los números."""
    s = res["sismo"]
    L = []
    w = L.append
    w("# %s" % titulo)
    w("")
    w("> **Predimensionamiento para anteproyecto.** No es el proyecto de cálculo estructural que exige el "
      "permiso de edificación: ese lo firma un ingeniero civil. Todos los números salen del modelo medido y de "
      "parámetros que están marcados según su fuente; **%s**." % res["veredicto"])
    w("")
    w("## 1. Sistema estructural (propuesta, estado: %s)" % res["propuesta"].get("estado", "propuesta"))
    w("")
    w(res["propuesta"]["sistema"] + ".")
    w("")
    w("Fundaciones: %s." % res["propuesta"]["fundaciones"])
    w("")
    w("## 2. Cargas (kN)")
    w("")
    w("| Peso propio | kN | | Sobrecarga | kN |")
    w("|---|---:|---|---|---:|")
    pk, lk = list(res["pesos_kN"].items()), list(res["sobrecargas_kN"].items())
    for i in range(max(len(pk), len(lk))):
        a = pk[i] if i < len(pk) else ("", "")
        b = lk[i] if i < len(lk) else ("", "")
        w("| %s | %s | | %s | %s |" % (a[0].replace("_", " "), f(a[1], 1) if a[1] != "" else "",
                                       b[0].replace("_", " "), f(b[1], 1) if b[1] != "" else ""))
    w("")
    w("Losa del 2º piso %s m²; cubiertas en planta %s m². Volúmenes de muros y losa: `model_extract.json` (medidos en el modelo FreeCAD)."
      % (f(res["area_losa_p2_m2"]), f(res["area_cubiertas_m2"])))
    w("")
    w("## 3. Sismo — método estático (NCh 433)")
    w("")
    w("Peso sísmico: nivel 2º piso (z = %s m) %s kN; nivel techo (z = %s m) %s kN; total P = %s kN."
      % (f(s["z_p2"]), f(s["P_nivel_p2_kN"], 1), f(s["z_techo"]), f(s["P_nivel_techo_kN"], 1), f(s["P_total_kN"], 1)))
    w("")
    w("Zona sísmica del sitio: **%s**; suelo: **%s** (site.json). %s"
      % (s["zona_sitio"] or "sin dato", s["suelo_sitio"] or "sin dato",
         "Sin estos datos se calcula cada escenario y se verifica el más desfavorable." if not s["del_sitio"] else ""))
    w("")
    w("| Zona | Suelo | C | Q0 (kN) | Corte 2º piso (kN) |")
    w("|---|---|---:|---:|---:|")
    for e in s["escenarios"]:
        w("| %s | %s | %s | %s | %s |" % (e["zona"], e["suelo"], f(e["C"], 3), f(e["Q0_kN"], 1), f(e["corte_p2_kN"], 1)))
    w("")
    c = res["caso_corte"]
    w("## 4. Muros: densidad y corte (caso zona %s, suelo %s)" % (c["zona"], c["suelo"]))
    w("")
    w("| Nivel | Dir. | Largo neto (m) | Área muros (m²) | Densidad (%) | σ0 (kPa) | Va (kN) | Q (kN) | Q/Va |")
    w("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for m in res["muros"]:
        w("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (m["nivel"], m["dir"], f(m["largo_neto_m"]), f(m["area_muros_m2"], 3),
                                                             f(m["densidad_pct"]), f(m["sigma0_kPa"], 1), f(m["Va_kN"], 1),
                                                             f(m["Q_kN"], 1), f(m["uso"], 3) if m["uso"] is not None else "—"))
    w("")
    w("Muros estructurales: espesor ≥ %s m, descontados los vanos. Va = (a·τm + b·σ0)·A (NCh 2123), con σ0 promedio del nivel. "
      "Q/Va < 1 indica capacidad suficiente **con parámetros sin transcribir**: no es veredicto." % f(res["propuesta"]["muros_estructurales_espesor_min_m"]))
    w("")
    vg = res["viga_eje_B"]
    w("## 5. Viga del eje B (luz %s m)" % f(vg["luz_m"]))
    w("")
    w("Muro del 2º piso sobre la viga %s kN/m; peso propio del descolgado %s kN/m; ancho tributario de losa %s m; D = %s kN/m, L = %s kN/m; wu = %s kN/m. "
      "Mu = %s kNm, Vu = %s kN. Predimensión: %s x %s m (h = L/%s, regla práctica); As ≈ %s cm² de acero inferior (φ = %s). %s."
      % (f(vg["muro_sobre_kN_m"]), f(vg["peso_propio_kN_m"]), f(vg["ancho_tributario_m"]), f(vg["D_kN_m"]), f(vg["L_kN_m"]), f(vg["wu_kN_m"]),
         f(vg["Mu_kNm"], 1), f(vg["Vu_kN"], 1), f(vg["b_m"]), f(vg["h_predim_m"]),
         f(v("predimension", "viga_L_sobre_h"), 0), f(vg["As_cm2"]), f(v("hormigon", "phi_flexion")), vg["nota"][0].upper() + vg["nota"][1:]))
    w("")
    vo = res["voladizo_patio"]
    w("## 6. Losa en voladizo sobre el patio (luz %s m)" % f(vo["luz_m"]))
    w("")
    w("wu = %s kN/m²; Mu = %s kNm/m; As ≈ %s cm²/m de acero superior. Espesor %s m vs mínimo práctico L/%s = %s m: %s."
      % (f(vo["wu_kN_m2"]), f(vo["Mu_kNm_por_m"]), f(vo["As_cm2_por_m"]), f(vo["espesor_m"]),
         f(v("predimension", "voladizo_L_sobre_h"), 0), f(vo["h_min_m"], 3), "suficiente" if vo["espesor_suficiente"] else "INSUFICIENTE"))
    w("")
    ls = res["losa_p2"]
    if ls:
        w("## 7. Losa del 2º piso")
        w("")
        w("Luz mayor (lado menor del recinto mayor bajo la losa: %s) %s m; espesor %s m vs L/%s = %s m: %s."
          % (ls["recinto"], f(ls["luz_m"]), f(ls["espesor_m"]), f(v("predimension", "losa_L_sobre_h_continua"), 0),
             f(ls["h_min_m"], 3), "suficiente" if ls["espesor_suficiente"] else "INSUFICIENTE"))
        w("")
    ci = res["cimientos"]
    w("## 8. Cimientos corridos")
    w("")
    w("Largo de muros estructurales del 1er piso %s m; carga de servicio media %s kN/m, máxima %s kN/m (muro con muro del 2º piso encima)."
      % (f(ci["largo_muros_p1_m"]), f(ci["q_media_kN_m"], 1), f(ci["q_max_kN_m"], 1)))
    w("")
    w("| σadm (kPa, escenario) | Ancho medio (m) | Ancho máximo (m) |")
    w("|---:|---:|---:|")
    for e in ci["escenarios"]:
        w("| %d | %s | %s |" % (e["sigma_adm_kPa"], f(e["b_media_m"]), f(e["b_max_m"])))
    w("")
    w("Anchos calculados = carga / σadm. Donde resultan menores que el muro que reciben (%s m), rige el ancho mínimo constructivo "
      "del cimiento, que fija el calculista; este cálculo no lo fija. "
      "La tensión admisible real sale del estudio de mecánica de suelos (DS 61 exige además clasificar el suelo)."
      % f(res["propuesta"]["muros_estructurales_espesor_min_m"]))
    w("")
    w("## 9. Parámetros sin transcribir")
    w("")
    w("Cada uno está en `tools/norms/estructura.json` con la norma de donde debe transcribirse: "
      + ", ".join("`%s`" % x for x in res["parametros_no_verificados"]) + ".")
    w("")
    w("## 10. Lo que sigue")
    w("")
    w("- Definir comuna (zona sísmica) y encargar el estudio de mecánica de suelos (suelo y σadm).")
    w("- Transcribir los parámetros desde NCh 433, NCh 1537, NCh 2123, NCh 3171 y NCh 204.")
    w("- Encargar el proyecto de cálculo a un ingeniero civil: este predimensionamiento es su punto de partida, no su reemplazo.")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--extract", required=True)
    ap.add_argument("--site")
    ap.add_argument("--propuesta", required=True)
    ap.add_argument("--recintos")
    ap.add_argument("-o", "--out")
    ap.add_argument("--memoria")
    ap.add_argument("--titulo", default="Memoria de cálculo estructural — predimensionamiento")
    a = ap.parse_args(argv)
    rd = lambda p: json.loads(Path(p).read_text(encoding="utf-8")) if p else None  # noqa: E731
    res = calcular(rd(a.spec), rd(a.extract), rd(a.site), rd(a.propuesta), rd(a.recintos))
    print("veredicto:", res["veredicto"])
    print("P total %.1f kN; peor escenario zona %s suelo %s: Q0 %.1f kN" % (
        res["sismo"]["P_total_kN"], res["sismo"]["peor"]["zona"], res["sismo"]["peor"]["suelo"], res["sismo"]["peor"]["Q0_kN"]))
    for m in res["muros"]:
        print("  %s %s densidad %.2f %%  Va %.1f kN  Q %.1f kN  Q/Va %s" % (m["nivel"], m["dir"], m["densidad_pct"], m["Va_kN"], m["Q_kN"], m["uso"]))
    vg = res["viga_eje_B"]
    print("viga eje B: wu %.2f kN/m  Mu %.1f kNm  %sx%s m  As %.2f cm2" % (vg["wu_kN_m"], vg["Mu_kNm"], vg["b_m"], vg["h_predim_m"], vg["As_cm2"]))
    print("voladizo: Mu %.2f kNm/m As %.2f cm2/m; losa:" % (res["voladizo_patio"]["Mu_kNm_por_m"], res["voladizo_patio"]["As_cm2_por_m"]), res["losa_p2"])
    print("cimientos:", res["cimientos"]["q_media_kN_m"], res["cimientos"]["q_max_kN_m"], res["cimientos"]["escenarios"])
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        print("escrito", a.out)
    if a.memoria:
        Path(a.memoria).write_text(memoria_md(res, a.titulo), encoding="utf-8")
        print("escrito", a.memoria)
    return 0


if __name__ == "__main__":
    sys.exit(main())
