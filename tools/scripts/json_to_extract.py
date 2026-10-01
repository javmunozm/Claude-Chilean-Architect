#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convierte una especificacion de planta (JSON del flujo croquis-a-3d) en el
model extract que consume tools/norm_check.py.

Las magnitudes salen de la geometria declarada en el JSON, no del cuadro de
superficies del documento: el objetivo es justamente poder contrastar ambos.

Uso:
    python tools/scripts/json_to_extract.py <planta.json> -o <extract.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def altura_libre(spec, level_id):
    """Altura piso a cielo de un nivel.

    El cielo lo define la losa del nivel superior, NO el muro mas alto: los
    hastiales y antepechos suben por encima del entrepiso y tomar el maximo da
    una altura que no existe en ningun recinto. Para el ultimo nivel (sin losa
    encima) se usa el muro mas bajo, que es la condicion critica bajo la
    cubierta inclinada.
    """
    levels = sorted(spec["levels"], key=lambda l: l["z"])
    z = {l["id"]: l["z"] for l in levels}[level_id]

    superior = [l for l in levels if l["z"] > z + 1e-6]
    if superior:
        z_sup = superior[0]["z"]
        for s in spec.get("slabs", []):
            if abs(s["z"] - z_sup) < 1e-6:
                return round(z_sup - z - s["t"], 3)
        return round(z_sup - z, 3)

    tops = [w["top"] for w in spec["walls"] if w["level"] == level_id]
    if not tops:
        return None
    # Ultimo nivel: el minimo es la altura critica al alero.
    return round(min(tops) - z, 3)


def stair_metrics(spec):
    out = []
    levels = {l["id"]: l["z"] for l in spec["levels"]}
    entrepiso = None
    if len(spec["levels"]) >= 2:
        entrepiso = spec["levels"][1]["z"] - spec["levels"][0]["z"]

    for i, st in enumerate(spec.get("stairs", [])):
        ch, hu = st["riser"], st["tread"]
        # build3d suma una alzada por cada descanso, ademas de los peldanos.
        n = sum(f["steps"] for f in st["flights"])
        n += sum(1 for f in st["flights"] if f.get("landing"))
        ancho = min(abs(f["x"][1] - f["x"][0]) for f in st["flights"])
        ent = {
            "name": "Escalera %d" % (i + 1),
            "kind": "stair",
            "tags": ["stair"],
            "riser": round(ch, 4),
            "tread": round(hu, 4),
            "steps": n,
            "rise_total": round(n * ch, 4),
            "min_width": round(ancho, 3),
            "blondel": round(2 * ch + hu, 4),
        }
        if entrepiso is not None:
            ent["floor_to_floor"] = round(entrepiso, 4)
            ent["rise_deficit"] = round(entrepiso - n * ch, 4)
        out.append(ent)
    return out


def slab_areas(spec):
    out = []
    for s in spec.get("slabs", []):
        area = sum((x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in s["rects"])
        out.append({
            "name": "Losa z=%.2f" % s["z"],
            "kind": "slab",
            "tags": ["slab"],
            "area": round(area, 3),
            "thickness": s["t"],
            "level_z": s["z"],
        })
    return out


def level_entities(spec):
    """Un pseudo-recinto por nivel, para verificar altura libre (OGUC 4.1.1)."""
    out = []
    for l in spec["levels"]:
        h = altura_libre(spec, l["id"])
        if h is None:
            continue
        out.append({
            "name": "Nivel %s (altura libre)" % l["id"],
            "kind": "space",
            "tags": ["habitable"],
            "clear_height": h,
            "level_z": l["z"],
            "_nota": ("altura piso a cielo del nivel; no sustituye la medicion "
                      "recinto por recinto"),
        })
    return out


def opening_entities(spec):
    out = []
    for i, o in enumerate(spec.get("openings", [])):
        x1, y1, x2, y2 = o["rect"]
        ancho = round(max(abs(x2 - x1), abs(y2 - y1)), 3)
        ent = {
            "name": "%s %d (%s)" % (o["kind"], i + 1, o["level"]),
            "kind": "door" if o["kind"] == "door" else "window",
            "tags": [o["kind"]],
            "nominal_width": ancho,
        }
        if o.get("head") is not None and o.get("sill") is not None:
            ent["opening_height"] = round(o["head"] - o["sill"], 3)
            ent["sill"] = o["sill"]
            ent["head"] = o["head"]
        # clear_width NO se deriva del ancho nominal: depende de marco y hoja.
        out.append(ent)
    return out


def build(spec, source):
    entities = []
    entities += level_entities(spec)
    entities += slab_areas(spec)
    entities += stair_metrics(spec)
    entities += opening_entities(spec)

    total = sum(e["area"] for e in entities if e["kind"] == "slab")
    return {
        "project": spec.get("meta", {}).get("titulo", Path(source).stem),
        "source_file": str(source),
        "generated_by": "tools/scripts/json_to_extract.py",
        "units": "m, m2",
        "entities": entities,
        "totals": {
            "slab_area": round(total, 3),
            "walls": len(spec.get("walls", [])),
            "openings": len(spec.get("openings", [])),
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("-o", "--out")
    args = ap.parse_args(argv)

    spec = json.load(open(args.spec, encoding="utf-8"))
    data = build(spec, args.spec)
    text = json.dumps(data, indent=2, ensure_ascii=False)

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("escrito %s (%d entidades, %.2f m2 de losa)"
              % (args.out, len(data["entities"]), data["totals"]["slab_area"]))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
