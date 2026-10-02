# -*- coding: utf-8 -*-
"""Decide bisagra y abatimiento de cada puerta según un patrón moderno de diseño.

Entradas : v2/calcs/plan_data.json  (cortes del FCStd: vanos, recintos netos, mobiliario, escalera)
Salida   : v2/plans/puertas_v2.json

Reglas (CONVENCIÓN DE DISEÑO, no norma: ningún artículo OGUC está transcrito en el repo,
de modo que ninguna regla se declara cumplimiento):
  R1  ancho >= 2,0 m con alto >= 2,3 m  -> corredera de vidrio, sin abatimiento.
  R2  ancho 1,2 - 2,0 m                 -> doble hoja batiente, abre hacia el lado exterior
                                           (porche/patio/paso); bisagras en ambas jambas.
  R3  puerta de acceso principal (lado exterior = porche) -> abre hacia el interior.
  R3b puerta a patio/paso desde una circulación -> abre hacia el exterior, para no
      bloquear la galería.
  R8  puerta entre dos circulaciones -> no abre hacia la escalera.
  R4  recinto <-> circulación            -> abre HACIA EL RECINTO, no hacia el pasillo.
  R5  recinto <-> baño/clóset/servicio   -> abre hacia el baño/clóset.
  R6  bisagra en la jamba más cercana a la esquina del recinto hacia el que abre, de modo
      que la hoja a 90 grados queda contra el muro y no cruza el recinto.
  R7  el arco de giro (cuarto de disco, radio = ancho libre) debe quedar DENTRO del recinto,
      sin cruzar mobiliario, escalera ni el arco de otra puerta. Si falla, se prueba la otra
      jamba y luego el otro lado; la regla que se aplicó queda registrada.

Los pasos sin hoja ("open") no llevan abatimiento.
"""
import json
import math
from pathlib import Path

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

V2 = Path(__file__).resolve().parents[1]
DATA = json.loads((V2 / "calcs" / "plan_data.json").read_text(encoding="utf-8"))
OUT = V2 / "plans" / "puertas_v2.json"

EXT_TIPOS = {"Porche", "Patio Interior", "Paso Cubierto", "Paso Descubierto"}
WET_SERV = ("baño", "clóset", "closet", "walk-in", "logia")
CIRC = ("pasillo", "hall", "escalera")


def clasifica(nombre):
    if nombre is None or nombre in EXT_TIPOS:
        return "ext"
    low = nombre.lower()
    if any(k in low for k in WET_SERV):
        return "wet"
    if any(k in low for k in CIRC):
        return "circ"
    return "room"


def sector(center, r, a0, a1, n=14):
    pts = [center]
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        pts.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a)))
    return Polygon(pts)


def angle_of(v):
    return math.atan2(v[1], v[0])


def arc_span(a_closed, a_open):
    """Extremos (a0, a1) del arco más corto de a_closed a a_open (cuarto de vuelta)."""
    d = (a_open - a_closed + math.pi) % (2 * math.pi) - math.pi
    return (a_closed, a_closed + d)


def plan_level(lv):
    pl = DATA["plantas"][lv]
    rooms = {r["label"]: Polygon(r["pts"]) for r in pl["recintos"]}

    def where(x, y):
        for n, pg in rooms.items():
            if pg.buffer(0.005).contains(Point(x, y)):
                return n
        return None

    obst = []
    for m in pl["mobiliario"]:
        obst.append(box(m["x0"], m["y0"], m["x1"], m["y1"]))
    if lv == "p1":
        for f in pl["escalera"]:
            if f["z"] < 1.2:                        # tramos que se pisan en este nivel
                obst.append(Polygon(f["pts"]))
    obst_u = unary_union(obst) if obst else None

    placed = []                                      # sectores ya asignados
    out = []
    doors = [v for v in pl["vanos"] if v["tipo"] == "door"]
    doors.sort(key=lambda v: v["codigo"])
    for v in doors:
        cx, cy, L, t = v["cx"], v["cy"], v["largo"], v["espesor_muro"]
        alto = v["dintel"] - v["antepecho"]
        hor = v["horizontal"]
        # normal 'positiva' y 'negativa' del muro; lado A = +, lado B = -
        nA = (0.0, 1.0) if hor else (1.0, 0.0)
        along = (1.0, 0.0) if hor else (0.0, 1.0)
        off = t / 2 + 0.3
        nameA = where(cx + nA[0] * off, cy + nA[1] * off)
        nameB = where(cx - nA[0] * off, cy - nA[1] * off)
        cA, cB = clasifica(nameA), clasifica(nameB)
        rec = {"codigo": v["codigo"], "nivel": lv, "ancho": L, "alto": round(alto, 3),
               "lado_A": nameA, "lado_B": nameB}
        # R1 corredera
        if L >= 2.0 and alto >= 2.3:
            rec.update(tipo="corredera", regla="R1 ventanal >= 2,0 m: corredera de vidrio")
            out.append(rec)
            continue
        double = 1.2 <= L < 2.0
        # lado hacia el que se prefiere abrir
        if double:
            order = ["A", "B"] if cA == "ext" else ["B", "A"]
            regla = "R2 doble hoja, abre hacia el exterior"
        elif "ext" in (cA, cB):
            ext_side = "A" if cA == "ext" else "B"
            ext_name = nameA if cA == "ext" else nameB
            inner_cls = cB if cA == "ext" else cA
            inward = ["B", "A"] if ext_side == "A" else ["A", "B"]
            if ext_name == "Porche" or inner_cls != "circ":
                order, regla = inward, "R3 acceso: abre hacia el interior"
            else:
                order = [ext_side, inward[0]]
                regla = "R3b puerta a exterior desde circulación: abre hacia el exterior"
        elif "circ" in (cA, cB) and not ({cA, cB} == {"circ"}):
            order = ["B", "A"] if cA == "circ" else ["A", "B"]
            regla = "R4 abre hacia el recinto, no hacia la circulación"
        elif {cA, cB} == {"circ"} and any((n or "").lower() == "escalera" for n in (nameA, nameB)):
            order = ["A", "B"] if (nameA or "").lower() != "escalera" else ["B", "A"]
            regla = "R8 no abre hacia la escalera"
        elif "wet" in (cA, cB):
            order = ["A", "B"] if cA == "wet" else ["B", "A"]
            regla = "R5 abre hacia el baño/clóset"
        else:
            order = ["A", "B"]
            regla = "abre hacia el lado A (sin regla específica)"

        cands = []
        for si, side in enumerate(order):
            sgn = 1 if side == "A" else -1
            n = (nA[0] * sgn, nA[1] * sgn)
            name = nameA if side == "A" else nameB
            room = rooms.get(name)
            face = (cx + n[0] * t / 2, cy + n[1] * t / 2)        # cara del muro del lado de giro
            half = L / 2.0 if double else L
            hinges = [(-1,), (1,)] if not double else [(-1, 1)]
            for hset in hinges:
                arcs, info = [], []
                for h in hset:
                    hp = (face[0] + along[0] * h * L / 2, face[1] + along[1] * h * L / 2)
                    closed = (-along[0] * h, -along[1] * h)          # hacia la otra jamba
                    a0, a1 = arc_span(angle_of(closed), angle_of(n))
                    arcs.append(sector(hp, half, a0, a1))
                    info.append({"bisagra": [round(hp[0], 4), round(hp[1], 4)], "radio": half,
                                 "a0_deg": round(math.degrees(a0), 2), "a1_deg": round(math.degrees(a1), 2),
                                 "jamba": h})
                # distancia de la bisagra a la esquina del recinto (sentido alejándose de la puerta)
                corner = 0.0
                if room is not None and not double:
                    h = hset[0]
                    probe = (face[0] + n[0] * 0.05, face[1] + n[1] * 0.05)
                    ray = [(probe[0] + along[0] * h * L / 2, probe[1] + along[1] * h * L / 2),
                           (probe[0] + along[0] * h * 12.0, probe[1] + along[1] * h * 12.0)]
                    from shapely.geometry import LineString
                    inter = room.boundary.intersection(LineString(ray))
                    corner = Point(ray[0]).distance(inter) if not inter.is_empty else 9.9
                ok_room = True if room is None else all(room.buffer(0.03).contains(a) for a in arcs)
                clash = []
                for a in arcs:
                    if obst_u is not None and a.intersection(obst_u).area > 0.01:
                        clash.append("mobiliario/escalera")
                    if any(a.intersection(p).area > 0.01 for p in placed):
                        clash.append("otro arco")
                score = (0 if (ok_room and not clash) else 1, si, corner)
                cands.append((score, side, n, name, info, arcs, ok_room, clash, corner))
        cands.sort(key=lambda c: c[0])
        score, side, n, name, info, arcs, ok_room, clash, corner = cands[0]
        placed.extend(arcs)
        # mano: observador en el lado opuesto al giro, mirando hacia el giro
        f = n
        right = (f[1], -f[0])
        mano = []
        for i in info:
            hp = i["bisagra"]
            s = (hp[0] - cx) * right[0] + (hp[1] - cy) * right[1]
            mano.append("derecha" if s > 0 else "izquierda")
        rec.update(tipo="doble hoja batiente" if double else "batiente", abre_hacia=name,
                   lado=side, normal=list(n), hojas=info, bisagra_mano=mano[0] if len(mano) == 1 else "ambos lados",
                   distancia_a_esquina=round(corner, 3), regla=regla,
                   verificacion={"arco_dentro_del_recinto": ok_room, "cruces": sorted(set(clash))})
        if score[0] == 1:
            rec["advertencia"] = "ningun candidato libre de cruces; se eligio el de menor puntaje"
        out.append(rec)
    return out


def main():
    res = {"_nota": ["Convención de diseño, no norma. Reglas R1-R7 en el docstring de derive_puertas.py.",
                     "Mano: observador en el lado desde el que se EMPUJA la puerta."],
           "niveles": {lv: plan_level(lv) for lv in ("p1", "p2")}}
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for lv, ds in res["niveles"].items():
        for d in ds:
            if d["tipo"] == "corredera":
                print(lv, d["codigo"], "corredera")
            else:
                print(lv, d["codigo"], d["tipo"], "-> abre hacia", d["abre_hacia"], "| bisagra", d["bisagra_mano"],
                      "| esquina %.2f" % d["distancia_a_esquina"], "|", d["regla"],
                      "| cruces:", d["verificacion"]["cruces"] or "-", "| dentro:", d["verificacion"]["arco_dentro_del_recinto"],
                      "| ADV" if "advertencia" in d else "")
    print("escrito", OUT)


if __name__ == "__main__":
    main()
