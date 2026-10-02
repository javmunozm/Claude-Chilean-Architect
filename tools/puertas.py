#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puertas en planta: abatimiento y bisagra, y puertas que faltan.

Herramienta compartida (intérprete del sistema: shapely). La usan
tools/scripts/json_to_dxf.py y projects/<P>/v2/plans/derive_puertas.py.

Hace dos cosas:

1. DECIDE cómo abre cada puerta que el modelo trae. Si el vano declara
   "operation", "hinge" o "swing", eso manda ("indicado en el modelo"). Si no, se
   infiere con las reglas de diseño R1-R9 (de v2/plans/derive_puertas.py):

   R1  ancho >= 2,0 m con alto >= 2,3 m  -> corredera de vidrio.
   R2  ancho 1,2-2,0 m                   -> doble hoja, abre hacia el exterior.
   R3  acceso desde el exterior           -> abre hacia el interior.
   R3b a patio/paso desde una circulación -> abre hacia el exterior (no bloquea el pasillo).
   R4  recinto <-> circulación            -> abre hacia el recinto.
   R5  recinto <-> baño/clóset/servicio   -> abre hacia el baño/clóset.
   R6  bisagra en la jamba más cercana a la esquina: la hoja abierta queda contra el muro.
   R7  el arco (radio = ancho) debe caer dentro del recinto, sin cruzar mobiliario,
       escalera ni otro arco; si no, prueba la otra jamba y luego el otro lado.
   R8  entre dos circulaciones no abre hacia la escalera.
   R9  baño accesible -> abre hacia afuera del baño (práctica habitual; la exigencia
       de OGUC 4.1.7 no está transcrita en rules.json: verificar con el texto oficial).

2. GENERA las puertas que el modelo no trae (política por defecto, POLITICA):
   - todo recinto tipo dormitorio (nombre con "dormitorio", "pieza", "habitación")
     lleva puerta PROPIA, aunque se llegue a él por un borde abierto;
   - todo otro recinto al que no se llega desde el acceso recibe una puerta;
   - escaleras y circulaciones (pasillo, hall, galería, pasarela...) NO reciben
     puerta generada: si quedan sin acceso se informa. Para generarlas, pedirlo
     en la línea de comandos (--puertas-circulacion).
   Busca el muro que comparte con un recinto accesible, prefiere una circulación,
   la ubica junto a la esquina para que la bisagra quede contra el muro y la valida
   con R7. Va marcada "generada": no estaba en el modelo, es una propuesta.
   Las puertas que el usuario indica en el modelo siempre mandan.

Nada de esto es norma: ningún artículo OGUC sobre puertas está transcrito en
tools/norms/rules.json. Los anchos por defecto (ANCHOS) son convención de diseño.

Entrada por nivel (marco cualquiera, metros):
    recintos   [{"label", "pts": [[x, y], ...], "tipo"?}]
    muros      [[[x, y], ...], ...]        polígonos de muro cortado
    vanos      [{"codigo", "tipo": door|window|open, "cx", "cy", "horizontal",
                 "largo", "espesor_muro", "antepecho", "dintel",
                 "operation"?, "hinge"?, "swing"?}]
    obstaculos [[[x, y], ...], ...]        mobiliario y tramos de escalera pisables

CLI (formato plan_data.json de v2):
    python tools/puertas.py <plan_data.json> -o <puertas.json> [--recintos <recintos.json>]
        [--puertas-circulacion] [--con-puerta <palabra> ...]
"""
from __future__ import annotations

import argparse
import json
import math
import sys

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep

# Anchos de hoja por defecto para puertas GENERADAS (convención de diseño, no norma).
ANCHOS = {"wet": 0.70, "room": 0.80, "circ": 0.90, "ext": 0.90}
HOLGURA_ESQUINA = 0.10          # de la cara del muro perpendicular a la jamba
SIN_ROTULO = "Recinto sin rótulo"
ALTO_PUERTA = 2.10              # dintel de las puertas generadas (convención)

EXT_NOMBRES = ("porche", "patio", "paso", "terraza", "jardín", "jardin", "exterior", "antejardín")
WET_SERV = ("baño", "bano", "clóset", "closet", "walk-in", "logia", "despensa", "bodega")
CIRC = ("pasillo", "hall", "escalera", "vestíbulo", "vestibulo", "galería", "galeria", "pasarela")
DORMITORIOS = ("dormitorio", "pieza", "habitación", "habitacion")

# Qué puertas se generan si el modelo no las trae (ver docstring, punto 2).
#   obligatorias: palabras de nombre de recinto que exigen puerta propia
#   circulacion:  si True, también se generan puertas hacia escaleras y circulaciones
POLITICA = {"obligatorias": DORMITORIOS, "circulacion": False}


def es_escalera(nombre):
    """El recinto de la escalera (no un 'Hall Escalera' ni un 'Vestíbulo escalera')."""
    return (nombre or "").strip().lower().startswith("escalera")


def clasifica(nombre, tipo=None):
    if nombre is None or tipo == "exterior":
        return "ext"
    low = nombre.lower()
    if any(k in low for k in EXT_NOMBRES) and tipo is None:
        return "ext"
    if any(k in low for k in WET_SERV):
        return "wet"
    if any(k in low for k in CIRC):
        return "circ"
    return "room"


def _sector(center, r, a0, a1, n=14):
    pts = [center]
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        pts.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a)))
    return Polygon(pts)


def _arc_span(a_closed, a_open):
    d = (a_open - a_closed + math.pi) % (2 * math.pi) - math.pi
    return a_closed, a_closed + d


class Nivel:
    """Geometría de un nivel y las consultas que necesitan las reglas."""

    def __init__(self, recintos, muros, vanos, obstaculos=()):
        self.recintos = recintos
        self.rooms = {r["label"]: Polygon(r["pts"]) for r in recintos}
        self.tipos = {r["label"]: r.get("tipo") for r in recintos}
        self.muros = [Polygon(m) for m in muros if len(m) >= 3]
        self.muros_u = unary_union(self.muros) if self.muros else Polygon()
        self.muros_p = prep(self.muros_u.buffer(1e-4))
        self.rooms_p = {n: prep(pg.buffer(0.005)) for n, pg in self.rooms.items()}
        self.vanos = vanos
        obs = [Polygon(o) for o in obstaculos if len(o) >= 3]
        self.obst = unary_union(obs) if obs else None

    def donde(self, x, y):
        p = Point(x, y)
        for n, pg in self.rooms_p.items():
            if pg.contains(p):
                return n
        return None

    def clase(self, nombre):
        return clasifica(nombre, self.tipos.get(nombre))

    def lados(self, v):
        nA = (0.0, 1.0) if v["horizontal"] else (1.0, 0.0)
        off = v["espesor_muro"] / 2 + 0.3
        a = self.donde(v["cx"] + nA[0] * off, v["cy"] + nA[1] * off)
        b = self.donde(v["cx"] - nA[0] * off, v["cy"] - nA[1] * off)
        return nA, a, b


# ------------------------------------------------------------------ abatimiento

def decidir(nivel, v, ocupados, lv=""):
    """Decisión para un vano de puerta. `ocupados` acumula los arcos ya asignados."""
    cx, cy, L, t = v["cx"], v["cy"], v["largo"], v["espesor_muro"]
    alto = v["dintel"] - v["antepecho"]
    hor = v["horizontal"]
    nA, nameA, nameB = nivel.lados(v)
    along = (1.0, 0.0) if hor else (0.0, 1.0)
    cA, cB = nivel.clase(nameA), nivel.clase(nameB)
    rec = {"codigo": v["codigo"], "nivel": lv, "ancho": L, "alto": round(alto, 3),
           "lado_A": nameA, "lado_B": nameB}

    op = v.get("operation")
    if op == "sliding" or (op is None and L >= 2.0 and alto >= 2.3):
        rec.update(tipo="corredera", regla="indicado en el modelo: corredera" if op
                   else "R1 ventanal >= 2,0 m: corredera de vidrio")
        return rec
    double = op == "double" or (op is None and 1.2 <= L < 2.0)

    swing = v.get("swing")
    if swing in (1, -1):
        order = ["A", "B"] if swing > 0 else ["B", "A"]
        order = order[:1]
        regla = "indicado en el modelo: abre hacia el lado %s" % ("+" if swing > 0 else "-")
    elif double:
        order = ["A", "B"] if cA == "ext" else ["B", "A"]
        regla = "R2 doble hoja, abre hacia el exterior"
    elif any(c == "wet" and "accesible" in (n or "").lower() for c, n in ((cA, nameA), (cB, nameB))):
        acc_a = cA == "wet" and "accesible" in (nameA or "").lower()
        order = ["B", "A"] if acc_a else ["A", "B"]
        regla = ("R9 baño accesible: abre hacia afuera del baño (práctica; OGUC 4.1.7 "
                 "no transcrita, verificar)")
    elif "ext" in (cA, cB):
        ext_side = "A" if cA == "ext" else "B"
        ext_name = nameA if cA == "ext" else nameB
        inner_cls = cB if cA == "ext" else cA
        inward = ["B", "A"] if ext_side == "A" else ["A", "B"]
        principal = ext_name is None or "porche" in (ext_name or "").lower() or "acceso" in (ext_name or "").lower()
        if principal or inner_cls != "circ":
            order, regla = inward, "R3 acceso: abre hacia el interior"
        else:
            order = [ext_side, inward[0]]
            regla = "R3b puerta a exterior desde circulación: abre hacia el exterior"
    elif "circ" in (cA, cB) and {cA, cB} != {"circ"}:
        order = ["B", "A"] if cA == "circ" else ["A", "B"]
        regla = "R4 abre hacia el recinto, no hacia la circulación"
    elif {cA, cB} == {"circ"} and any(es_escalera(n) for n in (nameA, nameB)):
        order = ["A", "B"] if not es_escalera(nameA) else ["B", "A"]
        regla = "R8 no abre hacia la escalera"
    elif "wet" in (cA, cB):
        order = ["A", "B"] if cA == "wet" else ["B", "A"]
        regla = "R5 abre hacia el baño/clóset"
    else:
        order = ["A", "B"]
        regla = "abre hacia el lado A (sin regla específica)"

    hinge = v.get("hinge")
    cands = []
    for si, side in enumerate(order):
        sgn = 1 if side == "A" else -1
        n = (nA[0] * sgn, nA[1] * sgn)
        name = nameA if side == "A" else nameB
        room = nivel.rooms.get(name)
        face = (cx + n[0] * t / 2, cy + n[1] * t / 2)
        half = L / 2.0 if double else L
        if double:
            hsets = [(-1, 1)]
        elif hinge in ("start", "end"):
            hsets = [(-1,)] if hinge == "start" else [(1,)]
        else:
            hsets = [(-1,), (1,)]
        for hset in hsets:
            arcs, info = [], []
            for h in hset:
                hp = (face[0] + along[0] * h * L / 2, face[1] + along[1] * h * L / 2)
                closed = (-along[0] * h, -along[1] * h)
                a0, a1 = _arc_span(math.atan2(closed[1], closed[0]), math.atan2(n[1], n[0]))
                arcs.append(_sector(hp, half, a0, a1))
                info.append({"bisagra": [round(hp[0], 4), round(hp[1], 4)], "radio": half,
                             "a0_deg": round(math.degrees(a0), 2), "a1_deg": round(math.degrees(a1), 2),
                             "jamba": h})
            corner = 0.0
            if room is not None and not double:
                h = hset[0]
                probe = (face[0] + n[0] * 0.05, face[1] + n[1] * 0.05)
                ray = [(probe[0] + along[0] * h * L / 2, probe[1] + along[1] * h * L / 2),
                       (probe[0] + along[0] * h * 12.0, probe[1] + along[1] * h * 12.0)]
                inter = room.boundary.intersection(LineString(ray))
                corner = Point(ray[0]).distance(inter) if not inter.is_empty else 9.9
            ok_room = True if room is None else all(room.buffer(0.03).contains(a) for a in arcs)
            clash = []
            for a in arcs:
                if nivel.obst is not None and a.intersection(nivel.obst).area > 0.01:
                    clash.append("mobiliario/escalera")
                if any(a.intersection(p).area > 0.01 for p in ocupados):
                    clash.append("otro arco")
            score = (0 if (ok_room and not clash) else 1, si, corner)
            cands.append((score, side, n, name, info, arcs, ok_room, clash, corner))
    cands.sort(key=lambda c: c[0])
    score, side, n, name, info, arcs, ok_room, clash, corner = cands[0]
    ocupados.extend(arcs)
    right = (n[1], -n[0])
    mano = ["derecha" if ((i["bisagra"][0] - cx) * right[0] + (i["bisagra"][1] - cy) * right[1]) > 0
            else "izquierda" for i in info]
    if side != order[0]:
        regla += "; R7: el arco no cabe hacia %s, abre hacia %s" % (
            (nameA if order[0] == "A" else nameB) or "exterior", name or "exterior")
    # sin recinto rotulado de ese lado es el exterior (clasifica(None) == "ext")
    rec.update(tipo="doble hoja batiente" if double else "batiente", abre_hacia=name or "exterior",
               lado=side, normal=list(n), hojas=info,
               bisagra_mano=mano[0] if len(mano) == 1 else "ambos lados",
               distancia_a_esquina=round(corner, 3), regla=regla,
               verificacion={"arco_dentro_del_recinto": ok_room, "cruces": sorted(set(clash))})
    if score[0] == 1:
        rec["advertencia"] = "ningun candidato libre de cruces; se eligio el de menor puntaje"
    return rec


# ------------------------------------------------------------------ conectividad

def grafo(nivel):
    """Aristas entre recintos: por puerta/paso, o por borde compartido sin muro."""
    G = {n: set() for n in nivel.rooms}
    G["EXTERIOR"] = set()
    for v in nivel.vanos:
        if v["tipo"] not in ("door", "open"):
            continue
        _, a, b = nivel.lados(v)
        a, b = a or "EXTERIOR", b or "EXTERIOR"
        G.setdefault(a, set()).add(b)
        G.setdefault(b, set()).add(a)
    nombres = list(nivel.rooms)
    libre = nivel.muros_u.buffer(0.01)
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            pa, pb = nivel.rooms[a], nivel.rooms[b]
            if pa.distance(pb) > 0.02:
                continue
            borde = pa.buffer(0.02).intersection(pb.buffer(0.02)).difference(libre)
            if not borde.is_empty and borde.area / 0.04 > 0.5:
                G[a].add(b)
                G[b].add(a)
    for n in nombres:                       # un recinto exterior conecta con el exterior
        if nivel.clase(n) == "ext":
            G[n].add("EXTERIOR")
            G["EXTERIOR"].add(n)
    return G


def alcanzables(nivel, G, inicio):
    seen = set(inicio)
    pila = list(inicio)
    while pila:
        x = pila.pop()
        for y in G.get(x, ()):
            if y not in seen:
                seen.add(y)
                pila.append(y)
    return seen


def inicio_de(nivel, G, es_planta_baja, puntos=()):
    """Desde dónde se entra: el exterior en planta baja; la escalera en los pisos.

    `puntos`: dónde llega la escalera (del modelo). El recinto que contiene cada punto,
    o el más cercano a menos de 1,5 m, es punto de partida: así no depende de que el
    rótulo "Escalera" caiga dentro de un recinto (en el piso superior suele caer en el
    vacío de la losa).
    """
    if es_planta_baja:
        return ["EXTERIOR"]
    desde = []
    for x, y in puntos:
        pt = Point(x, y)
        cerca = sorted(((pg.distance(pt), n) for n, pg in nivel.rooms.items()))
        if cerca and cerca[0][0] <= 1.5:
            desde.append(cerca[0][1])
    if desde:
        return desde
    esc = [n for n in nivel.rooms if es_escalera(n)]
    if esc:
        return esc
    circ = [n for n in nivel.rooms if nivel.clase(n) == "circ"]
    return [max(circ, key=lambda n: nivel.rooms[n].area)] if circ else []


# ------------------------------------------------------------------ puertas que faltan

def _tramos_compartidos(nivel, nombre, accesibles):
    """Tramos de muro entre `nombre` y un recinto accesible: [(vecino, p0, p1, t, n)].

    Recorre cada borde del recinto cada 5 cm; del otro lado del muro (medido) busca
    qué recinto hay. p0-p1 es el tramo sobre la cara del muro del lado del recinto,
    n la normal hacia el vecino y t el espesor de muro medido.
    """
    pg = nivel.rooms[nombre]
    coords = list(pg.exterior.coords)
    tramos = []
    for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 0.4:
            continue
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        # normal hacia afuera del recinto
        nx, ny = uy, -ux
        if pg.contains(Point((x0 + x1) / 2 + nx * 0.02, (y0 + y1) / 2 + ny * 0.02)):
            nx, ny = -nx, -ny
        muestras = []
        k = 0.05
        while k < L - 0.05 + 1e-9:
            px, py = x0 + ux * k, y0 + uy * k
            # espesor de muro: avanzar mientras se esté dentro de un muro
            t = 0.0
            while t < 0.6 and nivel.muros_p.contains(Point(px + nx * (t + 0.01), py + ny * (t + 0.01))):
                t += 0.01
            vecino = None
            if 0.05 <= t < 0.6:
                vecino = nivel.donde(px + nx * (t + 0.15), py + ny * (t + 0.15))
            muestras.append((k, vecino, round(t, 2)))
            k += 0.05
        # agrupar muestras contiguas con el mismo vecino accesible y espesor
        actual = None
        for k, vec, t in muestras + [(None, None, None)]:
            clave = (vec, t) if vec in accesibles else None
            if actual and (clave is None or clave != actual[0] or k is None):
                (vec0, t0), ka, kb = actual
                tramos.append((vec0, (x0 + ux * ka, y0 + uy * ka), (x0 + ux * kb, y0 + uy * kb),
                               t0, (nx, ny), (ux, uy)))
                actual = None
            if clave and actual is None:
                actual = [clave, k, k]
            elif clave and actual:
                actual[2] = k
    return tramos


def _libre_de_vanos(nivel, p0, p1):
    seg = LineString([p0, p1]).buffer(0.35)
    for v in nivel.vanos:
        if Point(v["cx"], v["cy"]).within(seg) or Point(v["cx"], v["cy"]).distance(seg) < v["largo"] / 2:
            return False
    return True


def prioridad_vecino(nivel, objetivo, vecino):
    """Con qué recinto conviene conectar: menor es mejor.

    Un baño, clóset o walk-in se sirve desde un dormitorio; un recinto, desde una
    circulación. Pasar por otro dormitorio o por el exterior queda al final.
    """
    c_obj, c_vec = nivel.clase(objetivo), nivel.clase(vecino)
    if c_obj == "wet":
        if "dormitorio" in (vecino or "").lower():
            return 0
        return {"circ": 1, "room": 2, "wet": 3, "ext": 5}.get(c_vec, 6)
    if c_vec == "room" and "dormitorio" in (vecino or "").lower():
        return 4
    return {"circ": 0, "room": 1, "wet": 3, "ext": 5}.get(c_vec, 6)


def tiene_puerta(nivel, nombre, tipos=("door",)):
    """¿Algún vano de esos tipos (del modelo o ya generado) da a este recinto?"""
    return any(v["tipo"] in tipos and nombre in nivel.lados(v)[1:] for v in nivel.vanos)


def _candidatos(nivel, nombre, ok, ocupados, prefijo, n_cod, lv):
    """Mejor posición de puerta para `nombre` en un muro hacia un recinto de `ok`."""
    mejor = None
    clase_r = nivel.clase(nombre)
    ancho = ANCHOS.get(clase_r, 0.80)
    for vec, p0, p1, t, nrm, u in _tramos_compartidos(nivel, nombre, ok):
        largo = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + 0.05
        if largo < ancho + HOLGURA_ESQUINA:
            continue
        prio = prioridad_vecino(nivel, nombre, vec)
        # posiciones: junto a cada esquina (R6) y cada 0,20 m entre ellas
        s_max = largo - HOLGURA_ESQUINA - ancho
        posiciones = {round(HOLGURA_ESQUINA, 3), round(s_max, 3)}
        k = HOLGURA_ESQUINA + 0.20
        while k < s_max:
            posiciones.add(round(k, 3))
            k += 0.20
        for s0 in sorted(posiciones):
            if s0 < 0:
                continue
            a = (p0[0] + u[0] * s0, p0[1] + u[1] * s0)
            b = (a[0] + u[0] * ancho, a[1] + u[1] * ancho)
            if not _libre_de_vanos(nivel, a, b):
                continue
            cxp = (a[0] + b[0]) / 2 + nrm[0] * t / 2
            cyp = (a[1] + b[1]) / 2 + nrm[1] * t / 2
            v = {"codigo": "%s%02d" % (prefijo, n_cod), "tipo": "door", "cx": round(cxp, 4),
                 "cy": round(cyp, 4), "horizontal": abs(u[0]) > abs(u[1]), "largo": ancho,
                 "espesor_muro": t, "antepecho": 0.0, "dintel": ALTO_PUERTA}
            prueba = decidir(nivel, v, list(ocupados), lv)
            ok_arco = prueba.get("verificacion", {}).get("arco_dentro_del_recinto", True) \
                and not prueba.get("verificacion", {}).get("cruces")
            forzada = "R7:" in prueba.get("regla", "")      # abre hacia el lado no preferido
            puntaje = (0 if ok_arco else 1, prio, 1 if forzada else 0,
                       prueba.get("distancia_a_esquina", 9.9))
            if mejor is None or puntaje < mejor[0]:
                mejor = (puntaje, nombre, vec, v)
    return mejor


def generar_faltantes(nivel, ocupados, lv="", es_planta_baja=True, prefijo="P", inicio=(),
                      politica=None):
    """Genera las puertas que el modelo no trae, según `politica` (por defecto POLITICA).

    - recinto tipo dormitorio sin puerta propia -> puerta propia;
    - recinto al que no se llega -> puerta (salvo escaleras y circulaciones, que solo se
      informan, a menos que politica["circulacion"] sea True).
    Devuelve (vanos, decisiones, sin_solucion, avisos): `sin_solucion` son recintos del
    programa a los que no se pudo dar acceso; `avisos`, lo que solo se informa (espacios
    sin rótulo, circulaciones sin acceso, dormitorios sin muro donde poner su puerta).
    """
    pol = dict(POLITICA, **(politica or {}))
    obligatorias = tuple(k.lower() for k in pol["obligatorias"])

    def exige_puerta(n):
        return nivel.clase(n) != "ext" and any(k in n.lower() for k in obligatorias)

    G = grafo(nivel)
    nuevos, decisiones, sin = [], [], []
    residuales, omitidas, sin_muro = set(), set(), []
    usados = {v["codigo"] for v in nivel.vanos}
    n_cod = 1 + max([int(c[1:]) for c in usados if c[:1] == prefijo and c[1:].isdigit()] or [0])
    for _ in range(2 * len(nivel.rooms)):
        partida = inicio_de(nivel, G, es_planta_baja, inicio)
        if not partida:
            sin.append("(no se sabe desde dónde se entra a este nivel)")
            break
        ok = alcanzables(nivel, G, partida)
        faltan = [n for n in nivel.rooms if n not in ok and nivel.clase(n) != "ext"]
        # un espacio sin rótulo (vacío, ducto, saliente de losa) no es un recinto del
        # programa: se informa, no se le inventa una puerta
        residuales.update(n for n in faltan if n.startswith(SIN_ROTULO))
        faltan = [n for n in faltan if not n.startswith(SIN_ROTULO)]
        # escaleras y circulaciones: sin puerta generada salvo que se pida
        if not pol["circulacion"]:
            omitidas.update(n for n in faltan if nivel.clase(n) == "circ")
            faltan = [n for n in faltan if nivel.clase(n) != "circ"]
        # un vano sin hoja ("open") hacia el dormitorio es una indicación del usuario: se respeta
        propias = [n for n in nivel.rooms if n in ok and exige_puerta(n)
                   and not tiene_puerta(nivel, n, ("door", "open")) and n not in sin_muro]
        objetivos = faltan + propias
        if not objetivos:
            break
        # primero los recintos principales: un baño o clóset suele quedar servido por
        # la puerta que ya tiene hacia su dormitorio, una vez que el dormitorio tiene acceso
        principales = [n for n in objetivos if nivel.clase(n) in ("room", "circ")]
        mejor = None
        for grupo in (principales, objetivos):
            for nombre in grupo:
                m = _candidatos(nivel, nombre, ok, ocupados, prefijo, n_cod, lv)
                if m and (mejor is None or m[0] < mejor[0]):
                    mejor = m
            if mejor:
                break
        if mejor is None:
            sin.extend(faltan)
            sin_muro.extend(propias)
            break
        puntaje, nombre, vec, v = mejor
        motivo = ("recinto sin acceso: %s" % nombre if nombre in faltan
                  else "dormitorio sin puerta propia: %s" % nombre)
        dec = decidir(nivel, v, ocupados, lv)
        dec.update(generada=True, motivo=motivo, conecta=[nombre, vec],
                   geometria={k: v[k] for k in ("cx", "cy", "horizontal", "largo", "espesor_muro",
                                                 "antepecho", "dintel")})
        if puntaje[0]:
            dec["advertencia"] = "el arco no queda libre en ninguna posicion probada"
        nivel.vanos.append(v)
        nuevos.append(v)
        decisiones.append(dec)
        G.setdefault(nombre, set()).add(vec)
        G.setdefault(vec, set()).add(nombre)
        n_cod += 1
    ok = alcanzables(nivel, G, inicio_de(nivel, G, es_planta_baja, inicio) or [])
    avisos = ["%s: %.2f m2 sin rotulo y sin acceso (vacio, ducto o saliente de losa?); "
              "no se genera puerta" % (n, nivel.rooms[n].area) for n in sorted(residuales)]
    avisos += ["%s: circulacion sin acceso; no se genera puerta (pedirla con "
               "--puertas-circulacion o indicarla en el modelo)" % n
               for n in sorted(omitidas) if n not in ok]
    avisos += ["%s: dormitorio sin puerta propia y sin muro libre hacia un recinto accesible; "
               "indicar la puerta en el modelo" % n for n in sin_muro]
    avisos += ["%s: se entra por un vano sin puerta indicado en el modelo; se respeta" % n
               for n in nivel.rooms if exige_puerta(n) and not tiene_puerta(nivel, n)
               and tiene_puerta(nivel, n, ("open",))]
    return nuevos, decisiones, sin, avisos


def resolver_nivel(recintos, muros, vanos, obstaculos=(), lv="", es_planta_baja=True, inicio=(),
                   politica=None):
    """Decisiones para las puertas del nivel + puertas generadas para recintos sin acceso.

    `inicio`: puntos de llegada de la escalera a este nivel (pisos superiores).
    `politica`: qué puertas generar (ver POLITICA).
    Devuelve (decisiones, sin_solucion, avisos).
    """
    nivel = Nivel(recintos, muros, [dict(v) for v in vanos], obstaculos)
    ocupados = []
    out = []
    for v in sorted((v for v in nivel.vanos if v["tipo"] == "door"), key=lambda v: v["codigo"]):
        out.append(decidir(nivel, v, ocupados, lv))
    _, generadas, sin, resid = generar_faltantes(nivel, ocupados, lv, es_planta_baja, inicio=inicio,
                                                 politica=politica)
    return out + generadas, sin, resid


# ------------------------------------------------------------------ recintos sin polígono

def regiones_desde_muros(huella, muros, rotulos=(), area_min=0.3):
    """Recintos derivados de la planta: el espacio libre entre muros, rotulado.

    Para proyectos cuyo JSON de recintos solo trae un punto de rótulo por recinto.
    `huella`: polígono del nivel (losa); `muros`: polígonos SIN cortar por los vanos
    (una puerta no une dos recintos en un solo espacio); `rotulos`:
    [{"nombre", "punto": [x, y], "tipo"?}]. Un espacio con dos rótulos (planta libre)
    lleva ambos nombres; uno sin rótulo queda como "Recinto sin rótulo N".
    """
    libre = huella.difference(unary_union([Polygon(m) for m in muros]).buffer(1e-3))
    piezas = [g for g in getattr(libre, "geoms", [libre]) if g.area >= area_min]
    piezas.sort(key=lambda g: -g.area)
    out = []
    n_sin = 0
    for g in piezas:
        dentro = [r for r in rotulos if g.contains(Point(*r["punto"]))]
        if dentro:
            label = " + ".join(r["nombre"] for r in dentro)
            tipo = dentro[0].get("tipo")
        else:
            n_sin += 1
            label, tipo = "%s %d" % (SIN_ROTULO, n_sin), None
        out.append({"label": label, "pts": [list(c) for c in g.exterior.coords][:-1], "tipo": tipo})
    return out


# ------------------------------------------------------------------ CLI (plan_data de v2)

def desde_plan_data(data, recintos_doc=None, politica=None):
    """Aplica resolver_nivel a cada planta de un plan_data.json (formato de v2)."""
    tipos = {}
    if recintos_doc:
        for lv, nv in recintos_doc.get("niveles", {}).items():
            for r in nv.get("recintos", []):
                tipos[(lv, r.get("label"))] = r.get("tipo")
    res = {"_nota": ["Convención de diseño, no norma (tools/puertas.py, reglas R1-R9).",
                     "Mano: observador en el lado desde el que se EMPUJA la puerta.",
                     "generada=true: puerta que el modelo no trae (dormitorio sin puerta propia "
                     "o recinto sin acceso); es una propuesta."],
           "niveles": {}, "sin_solucion": {}, "residuales": {}}
    orden = sorted(data["plantas"], key=lambda lv: data.get("levels", {}).get(lv, 0))
    for i, lv in enumerate(orden):
        pl = data["plantas"][lv]
        recs = [{"label": r["label"], "pts": r["pts"], "tipo": tipos.get((lv, r["label"]))}
                for r in pl["recintos"]]
        obst = [[(m["x0"], m["y0"]), (m["x1"], m["y0"]), (m["x1"], m["y1"]), (m["x0"], m["y1"])]
                for m in pl.get("mobiliario", [])]
        if i == 0:                                       # tramos que se pisan en la planta baja
            obst += [f["pts"] for f in pl.get("escalera", []) if f["z"] < 1.2]
        decs, sin, resid = resolver_nivel(recs, pl["muros"], pl["vanos"], obst, lv, es_planta_baja=(i == 0),
                                          politica=politica)
        res["niveles"][lv] = decs
        if sin:
            res["sin_solucion"][lv] = sin
        if resid:
            res["residuales"][lv] = resid
    return res


def agregar_opciones(ap):
    """Opciones de línea de comandos de la política de puertas (compartidas por los scripts)."""
    ap.add_argument("--puertas-circulacion", action="store_true",
                    help="generar también puertas hacia escaleras y circulaciones sin acceso")
    ap.add_argument("--con-puerta", action="append", default=[], metavar="PALABRA",
                    help="recintos cuyo nombre contiene PALABRA llevan puerta propia "
                         "(se suma a: %s)" % ", ".join(DORMITORIOS))


def politica_de_args(args):
    return {"obligatorias": DORMITORIOS + tuple(args.con_puerta),
            "circulacion": args.puertas_circulacion}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan_data")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--recintos")
    agregar_opciones(ap)
    args = ap.parse_args(argv)
    data = json.load(open(args.plan_data, encoding="utf-8"))
    rec = json.load(open(args.recintos, encoding="utf-8")) if args.recintos else None
    res = desde_plan_data(data, rec, politica_de_args(args))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False)
    for lv, ds in res["niveles"].items():
        for d in ds:
            gen = "GENERADA " if d.get("generada") else ""
            if d["tipo"] == "corredera":
                print(lv, d["codigo"], gen + "corredera")
            else:
                print(lv, d["codigo"], gen + d["tipo"], "-> abre hacia", d["abre_hacia"],
                      "| bisagra", d["bisagra_mano"], "|", d["regla"],
                      "| cruces:", d["verificacion"]["cruces"] or "-",
                      "| ADV" if "advertencia" in d else "")
    for lv, sin in res["sin_solucion"].items():
        print("SIN SOLUCION", lv, sin)
    for lv, rs in res["residuales"].items():
        for r in rs:
            print("AVISO", lv, r)
    print("escrito", args.out)
    return 1 if res["sin_solucion"] else 0


if __name__ == "__main__":
    sys.exit(main())
