# -*- coding: utf-8 -*-
"""Especificaciones técnicas (EETT) y cubicación de v5, con cantidades medidas.

    python make_eett.py          (intérprete del sistema: shapely)

Entradas:  v5/calcs/model_extract.json      volúmenes, áreas, vanos, escalera (medidos en el FCStd)
           ../v0/source/casa_rev_h.json     geometría de origen (fachadas, pavimentos, cubiertas)
           v5/calcs/aguas_lluvias.json      canales y bajadas (tools/aguas_lluvias.py)
           v5/calcs/estructura_calc.json    predimensionamiento (tools/estructura.py)
           v5/source/terminaciones.json     partidas de terminación (propuesta)
           v5/source/estructura.json        sistema estructural (propuesta)
Salidas:   v5/exports/eett_v5.md (+ .pdf con tools/md_pdf.py)
           v5/exports/cubicacion_v5.csv     partida, unidad, cantidad, fuente; precios vacíos

Cada cantidad dice de dónde sale. Ningún precio se escribe: son datos de mercado con
fecha y fuente, y no hay ninguno registrado. Las partidas cuya definición es una
propuesta lo dicen; las que dependen del calculista o de un estudio que no existe no
se cubican.
"""
import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

VER = Path(__file__).resolve().parents[1]
RAIZ = VER.parents[3]
sys.path.insert(0, str(RAIZ / "tools"))
_spec = importlib.util.spec_from_file_location("cubierta", RAIZ / "tools" / "cubierta.py")
cubierta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cubierta)
import md_pdf  # noqa: E402

rd = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
EXT = rd(VER / "calcs" / "model_extract.json")
SPEC = rd(VER.parent / "v0" / "source" / "casa_rev_h.json")
AGUAS = rd(VER / "calcs" / "aguas_lluvias.json")
CALC = rd(VER / "calcs" / "estructura_calc.json")
TERM = {t["id"]: t for t in rd(VER / "source" / "terminaciones.json")["partidas"]}
EST = rd(VER / "source" / "estructura.json")
SITIO = rd(VER.parents[1] / "site.json")
PROY = rd(VER / "source" / "proyecto.json")

ENT = EXT["entities"]
NIV = {l["id"]: l["z"] for l in SPEC["levels"]}
Z_TERRENO = SPEC["ground"]["z"]
T_EST = EST["muros_estructurales_espesor_min_m"]


def f(v, n=2):
    return ("{:,.%df}" % n).format(v).replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------ cubicación

def muros():
    """Superficie (largo x alto) y volumen de los muros medidos, por espesor y nivel."""
    out = {}
    for e in ENT:
        if e["kind"] != "wall":
            continue
        nom = e["name"]
        grupo = "hastial" if nom.startswith("Hastial") else "cierre" if nom.startswith("Cierre") else \
            ("p1" if " p1 " in nom + " " else "p2")
        if grupo in ("hastial", "cierre"):     # el extract no les mide largo ni espesor: solo volumen
            clase = "bajo_cubierta"
        else:
            clase = "estructural" if e.get("thickness", 0) >= T_EST - 1e-6 else "tabique"
        k = (grupo, clase)
        o = out.setdefault(k, {"n": 0, "largo": 0.0, "area": 0.0, "vol": 0.0})
        o["n"] += 1
        o["largo"] += e.get("length", 0.0)
        o["area"] += e.get("length", 0.0) * e.get("height", 0.0)
        o["vol"] += e.get("volume", 0.0)
    return out


def huella(nivel):
    rects = [s for s in SPEC["slabs"] if s["z"] == NIV[nivel]][0]["rects"]
    return unary_union([box(*r) for r in rects]).buffer(1e-6)


def fachadas():
    """Paños de muro exterior: muro estructural con un lado fuera de la huella de su nivel.

    Alto del paño: p1 desde el terreno hasta el 2º piso (incluye el canto de losa), p2
    desde el 2º piso hasta el coronamiento. Se descuentan los vanos de esos muros. Los
    hastiales se suman por su perfil. Sale de la geometría de origen del modelo.
    """
    hu = {"p1": huella("p1"), "p2": Polygon(huella("p2").exterior)}
    hu["p1"] = unary_union([hu["p1"], hu["p2"]])          # el voladizo del 2º piso también cubre
    paños, largo_zocalo = [], 0.0
    for w in SPEC["walls"]:
        if w["t"] < T_EST - 1e-6:
            continue
        a, b = w["a"], w["b"]
        L = math.dist(a, b)
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d = w["t"] + 0.05
        lados = [Point(m[0] + nx * d * s, m[1] + ny * d * s) for s in (1, -1)]
        base = Polygon(huella(w["level"]).exterior) if w["level"] == "p2" else huella("p1")
        if all(base.contains(p) for p in lados):
            continue
        z0 = Z_TERRENO if w["level"] == "p1" else NIV["p2"]
        z1 = NIV["p2"] if w["level"] == "p1" else w["top"]
        linea = LineString([a, b])
        vanos = sum((o["rect"][2] - o["rect"][0] + o["rect"][3] - o["rect"][1] - w["t"]) * (o["head"] - o["sill"])
                    for o in SPEC["openings"] if o["level"] == w["level"]
                    and box(*o["rect"]).buffer(0.01).intersection(linea).length > 0.05)
        paños.append({"nivel": w["level"], "largo": L, "bruta": L * (z1 - z0), "vanos": vanos})
        if w["level"] == "p1":
            largo_zocalo += L
    hast = sum(Polygon([(u, z) for u, z in g["profile"]] + [(g["profile"][-1][0], g["profile"][0][1])]).area
               for g in SPEC["gables"])
    return paños, hast, largo_zocalo


def cubiertas():
    out = []
    for r, e in zip(SPEC["roofs"], [x for x in ENT if x["kind"] == "roof"]):
        planta = unary_union([box(*rc) for rc in cubierta.rects_cubierta(r)]).area
        if r["type"] == "gable":
            s = (r["ridge_z"] - r["eave_z"]) / (r["ridge_x"] - r["x_ref"][0])
        else:
            s = abs(r["from"][1] - r["to"][1]) / abs(r["to"][0] - r["from"][0])
        out.append({"nombre": e["name"], "planta": planta, "pend": s, "inclinada": planta * math.sqrt(1 + s * s),
                    "vol_t": e["volume"] / r["t"]})
    return out


def pavimentos_ext():
    p = SPEC["paving"][0]
    return unary_union([box(*r) for r in p["rects"]]).area


def vanos_por_tipo(kind):
    g = {}
    for e in ENT:
        if e["kind"] == kind:
            k = (round(e["width"], 2), round(e["height"], 2))
            g.setdefault(k, 0)
            g[k] += 1
    return sorted(g.items(), key=lambda kv: (-kv[0][0] * kv[0][1]))


# ------------------------------------------------------------------ documento

def main():
    M = muros()
    paños, hastiales, L_zoc = fachadas()
    cubs = cubiertas()
    losas = {e["level_z"]: e for e in ENT if e["kind"] == "slab"}
    esc = next(e for e in ENT if e["kind"] == "stair")
    ven, pue = vanos_por_tipo("window"), vanos_por_tipo("door")
    can = AGUAS["canales"]
    baj = AGUAS["bajadas"]
    alto_zoc = TERM[2]["altura_m"] - Z_TERRENO
    bruta = sum(p["bruta"] for p in paños) + hastiales
    vanos = sum(p["vanos"] for p in paños)
    zocalo = L_zoc * alto_zoc
    estuco = bruta - vanos - zocalo
    vg = CALC["viga_eje_B"]

    filas = []          # cubicación: (partida, descripción, unidad, cantidad, fuente)

    def item(p, d, u, q, fu):
        filas.append((p, d, u, q, fu))
        return "| %s | %s | %s | %s | %s |" % (p, d, u, f(q) if isinstance(q, float) else q, fu)

    L = []
    w = L.append
    w("# Especificaciones técnicas — %s, versión %s" % (PROY.get("nombre") or "Vivienda", VER.name))
    w("")
    w("> **Documento PROVISIONAL.** Las revisiones normativas están INCONCLUSAS (umbrales sin transcribir, "
      "comuna y zonas del sitio en null). Los materiales son **propuestas** de los agentes facade-designer y "
      "structural-calculator hasta que el usuario o el arquitecto los confirme. Las cantidades se midieron en el "
      "modelo; los precios no se escriben (no hay ninguno con fecha y fuente).")
    w("")
    w("## A. Generalidades")
    w("")
    w("- Proyecto: %s. Propietario: %s. Arquitecto: %s." % tuple(PROY.get(k) or "por definir" for k in ("nombre", "propietario", "arquitecto")))
    w("- Dirección: %s. Comuna: %s. Rol: %s." % tuple(SITIO.get(k) or "por definir" for k in ("address", "comuna", "rol")))
    w("- Documentos que complementan estas EETT: `planos_%s.pdf` (6 láminas, incluye detalles D1–D5) y "
      "`memoria_calculo_%s.pdf` (predimensionamiento estructural)." % (VER.name, VER.name))
    w("- Cantidades: `calcs/model_extract.json` (FreeCAD), `calcs/aguas_lluvias.json`, `calcs/estructura_calc.json` "
      "y la geometría de origen; el detalle de cada una está en la columna *fuente* y en `cubicacion_%s.csv`." % VER.name)
    w("- Normas citadas sin artículo: están por transcribir en `tools/norms/`. Una partida que cita una norma así "
      "no se declara conforme.")
    w("")
    w("## B. Obra gruesa")
    w("")
    w("### B.1 Fundaciones")
    w("")
    w("%s. **No se cubica**: ancho y profundidad los fija el calculista con el estudio de mecánica de suelos "
      "(memoria §8 da anchos de cálculo de %s a %s m para σadm de 100 a 200 kPa, escenarios; rige el mínimo "
      "constructivo). Esquema en el detalle D3."
      % (EST["fundaciones"], f(min(e["b_max_m"] for e in CALC["cimientos"]["escenarios"])),
         f(max(e["b_max_m"] for e in CALC["cimientos"]["escenarios"]))))
    w("")
    w("| Ítem | Descripción | Unidad | Cantidad | Fuente |")
    w("|---|---|---|---:|---|")
    lp1, lp2 = losas[0.0], losas[NIV["p2"]]
    w(item("B.2", "Losa / radier del 1er piso, e = %s m" % f(lp1["thickness"]), "m²", lp1["area"], "model_extract (losa p1)"))
    w(item("B.2", "ídem, volumen de hormigón", "m³", lp1["volume"], "model_extract (losa p1)"))
    for (g, c), o in sorted(M.items()):
        if c != "estructural":
            continue
        nom = {"p1": "Muros de albañilería confinada 0,20 m, 1er piso", "p2": "Muros de albañilería confinada 0,20 m, 2º piso",
               "hastial": "Hastiales 0,20 m", "cierre": "Cierres bajo cubierta 0,20 m"}[g]
        w(item("B.3", nom + " (%d muros, %s m)" % (o["n"], f(o["largo"])), "m²", o["area"], "model_extract, largo x alto"))
    hc = [o for (g, c), o in M.items() if c == "bajo_cubierta"]
    w(item("B.3", "Hastiales y cierres bajo cubierta (%d piezas), volumen" % sum(o["n"] for o in hc), "m³",
           sum(o["vol"] for o in hc), "model_extract (sin largo ni espesor medidos)"))
    w(item("B.3", "Muros de 0,20 m, volumen total", "m³", sum(o["vol"] for (g, c), o in M.items() if c == "estructural"),
           "model_extract (vanos descontados)"))
    w(item("B.4", "Losa de hormigón armado del 2º piso, e = %s m" % f(lp2["thickness"]), "m²", lp2["area"], "model_extract (losa p2)"))
    w(item("B.4", "ídem, volumen de hormigón", "m³", lp2["volume"], "model_extract (losa p2)"))
    w(item("B.5", "Viga del eje B, %s x %s x %s m (predimensión)" % (f(vg["b_m"]), f(vg["h_predim_m"]), f(vg["luz_m"])),
           "m³", vg["b_m"] * vg["h_predim_m"] * vg["luz_m"], "estructura_calc (predimensionamiento)"))
    w(item("B.6", "Escalera de hormigón armado, %d contrahuellas de %s m, huella %s m" % (esc["steps"], f(esc["riser"], 4), f(esc["tread"], 3)),
           "gl", "1", "model_extract (escalera)"))
    for c in cubs:
        w(item("B.7", "Estructura de cubierta: %s, pendiente %s %%" % (c["nombre"], f(100 * c["pend"], 1)),
               "m²", c["inclinada"], "planta %s m² x √(1+p²)" % f(c["planta"])))
    w("")
    w("- **B.2–B.6 Hormigones y armaduras.** Hormigón y acero según el proyecto de cálculo (NCh 430, NCh 204: sin "
      "transcribir). Grado de hormigón, recubrimientos y armaduras: **los fija el calculista**; esta EETT no los inventa.")
    w("- **B.3 Albañilería confinada.** %s. Diseño y ejecución según NCh 2123 (sin transcribir), con pilares y cadenas "
      "de hormigón armado según el proyecto de cálculo. Densidad de muros y corte: memoria §4 (predimensionamiento)." % EST["sistema"].split(";")[0])
    w("- **B.4 Losa del 2º piso.** Vuela %s m sobre el patio (memoria §6). Espesor %s m (estructura.json, propuesta)."
      % (f(EST["voladizo_patio"]["luz_m"]), f(EST["losa_p2"]["espesor_m"])))
    w("- **B.7 Cubierta.** Estructura de madera (estructura.json, propuesta); escuadrías por el calculista. "
      "Superficie inclinada = planta x √(1+p²) (%s m²). Referencia, no control: volumen del sólido modelado / espesor = %s m² "
      "(el modelo extruye el espesor de cubierta en vertical, así que esa cifra se acerca a la planta, no a la inclinada)."
      % (" + ".join(f(c["inclinada"]) for c in cubs), " + ".join(f(c["vol_t"]) for c in cubs)))
    w("")
    w("## C. Tabiquería")
    w("")
    w("| Ítem | Descripción | Unidad | Cantidad | Fuente |")
    w("|---|---|---|---:|---|")
    for (g, c), o in sorted(M.items()):
        if c == "tabique":
            w(item("C.1", "Tabique liviano 0,12 m, %s (%d tabiques, %s m)" % ({"p1": "1er piso", "p2": "2º piso"}.get(g, g), o["n"], f(o["largo"])),
                   "m²", o["area"], "model_extract, largo x alto"))
    w("")
    w("Tabiques interiores no estructurales (estructura.json, propuesta). Composición y aislación acústica: por definir.")
    w("")
    w("## D. Terminaciones exteriores (propuesta, terminaciones.json)")
    w("")
    w("| Ítem | Descripción | Unidad | Cantidad | Fuente |")
    w("|---|---|---|---:|---|")
    w(item("D.1", "%s, %s" % (TERM[1]["terminacion"], TERM[1]["color"]), "m²", estuco,
           "fachada bruta %s − vanos %s − zócalo %s" % (f(bruta), f(vanos), f(zocalo))))
    w(item("D.2", "Zócalo: %s, altura terreno a +%s" % (TERM[2]["terminacion"], f(TERM[2]["altura_m"])), "m²", zocalo,
           "%s m de muro exterior del 1er piso x %s m" % (f(L_zoc), f(alto_zoc))))
    w(item("D.3", "Cubierta: %s, %s" % (TERM[3]["terminacion"], TERM[3]["color"]), "m²", sum(c["inclinada"] for c in cubs),
           "superficie inclinada (B.7)"))
    w(item("D.4", "Tapacán y forro de alero: %s" % TERM[4]["terminacion"].split(":")[0], "m", sum(c["largo"] for c in can if c["tipo"] == "alero"),
           "largo de aleros con canal (aguas_lluvias)"))
    w(item("D.5", "Pavimento exterior: %s" % TERM[8]["terminacion"], "m²", pavimentos_ext(), "rectángulos de pavimento de la geometría de origen"))
    w("")
    w("- Fachada bruta: paños de muro de 0,20 m con un lado fuera de la huella de su nivel, más hastiales "
      "(%s m²); el 1er piso desde el terreno (%s) hasta +%s, el 2º hasta el coronamiento. Vanos descontados: ancho x "
      "(dintel − alféizar) de los vanos de esos muros." % (f(hastiales), f(Z_TERRENO), f(NIV["p2"])))
    w("- Espesor de estuco %d mm; ninguna transmitancia se declara aquí: la verifica thermal-reviewer "
      "(OGUC 4.1.10 / DS 15, sin transcribir)." % TERM[1]["espesor_mm"])
    w("")
    w("## E. Ventanas y puertas")
    w("")
    w("| Ítem | Descripción | Unidad | Cantidad | Fuente |")
    w("|---|---|---|---:|---|")
    for (an, al), n in ven:
        w(item("E.1", "Ventana %s x %s m — %s" % (f(an), f(al), TERM[6]["terminacion"]), "u", str(n), "model_extract (ventanas)"))
    for (an, al), n in pue:
        w(item("E.2", "Puerta %s x %s m" % (f(an), f(al)), "u", str(n), "model_extract (puertas)"))
    w("")
    w("Superficie total de ventanas medida: %s m². Puerta de acceso (P01): %s (terminaciones.json, partida 7). "
      "Puertas interiores: material por definir. Herrajes y sentido de apertura: planos de planta (tools/puertas.py)."
      % (f(EXT["totals"]["window_area"]), TERM[7]["terminacion"]))
    w("")
    w("## F. Aguas lluvias")
    w("")
    w("| Ítem | Descripción | Unidad | Cantidad | Fuente |")
    w("|---|---|---|---:|---|")
    pa = AGUAS["parametros"]
    sec = "%s x %s m" % (f(pa["canal_ancho_m"]["value"]), f(pa["canal_alto_m"]["value"]))
    w(item("F.1", "Canal de alero %s, %s" % (sec, TERM[5]["terminacion"]), "m",
           sum(c["largo"] for c in can if c["tipo"] == "alero"), "aguas_lluvias (%d canales)" % sum(c["tipo"] == "alero" for c in can)))
    w(item("F.2", "Canal de encuentro con muro, con forro y babeta", "m",
           sum(c["largo"] for c in can if c["tipo"] == "encuentro"), "aguas_lluvias (%d canales)" % sum(c["tipo"] == "encuentro" for c in can)))
    w(item("F.3", "Bajada %s x %s m, acero prepintado" % (f(pa["bajada_lado_m"]["value"]), f(pa["bajada_lado_m"]["value"])), "m",
           sum(b["z_canal"] - b["z_suelo"] for b in baj), "aguas_lluvias (%d bajadas, z canal − z descarga)" % len(baj)))
    w("")
    a_terreno = sum(1 for b in baj if b["descarga"] == "a terreno")
    w("%d bajadas descargan a terreno y %d sobre una cubierta más baja (cuadro en la lámina 3). Disposición final de "
      "las aguas lluvias en el terreno: fuera del alcance de v5 (terreno no incluido). Verificación hidráulica: "
      "INCONCLUSA mientras `rainfall_intensity_mm_h` esté en null en site.json." % (a_terreno, len(baj) - a_terreno))
    w("")
    w("## G. Instalaciones")
    w("")
    w("No forman parte de v5: las revisa installations-reviewer (NCh Elec. 4/2003, NCh 2485). Sin partida.")
    w("")
    w("## H. Pendientes que estas EETT no resuelven")
    w("")
    w("- Confirmar las propuestas de terminaciones.json y estructura.json.")
    w("- Proyecto de cálculo firmado (fundaciones, armaduras, grado de hormigón, escuadrías de cubierta).")
    w("- Estudio de mecánica de suelos; comuna, zona sísmica y zona térmica del sitio.")
    w("- Precios unitarios con fecha y fuente (columna vacía en la cubicación).")
    w("- Terreno (fuera de alcance de v5): movimiento de tierras, drenaje y disposición de aguas lluvias.")
    md = VER / "exports" / ("eett_%s.md" % VER.name)
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("escrito", md)
    csv_p = VER / "exports" / ("cubicacion_%s.csv" % VER.name)
    with csv_p.open("w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh)
        cw.writerow(["partida", "descripcion", "unidad", "cantidad", "fuente", "precio_unitario", "total"])
        for p, d, u, q, fu in filas:
            cw.writerow([p, d, u, round(q, 3) if isinstance(q, float) else q, fu, "", ""])
    print("escrito", csv_p, "(%d partidas, precios vacíos)" % len(filas))
    md_pdf.convertir(md)


if __name__ == "__main__":
    main()
