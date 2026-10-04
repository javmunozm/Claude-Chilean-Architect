# -*- coding: utf-8 -*-
"""Utilidades compartidas por build_model.py, measure_v5.py y export_slices.py.

Corre DENTRO del intérprete de FreeCAD (importa Part). Todo en milímetros salvo
donde el nombre diga _m.
"""
import math

import FreeCAD
import Part
from FreeCAD import Vector as V

MM = 1000.0
YOFF = 14.0          # el JSON usa Y desde el frente (Y=0); el modelo traslada Y -= 14 m
                     # para que el origen sea la esquina NO de la envolvente, +Y norte


def P(x, y, z=0.0):
    """Coordenadas del documento (m) -> punto FreeCAD (mm)."""
    return V(x * MM, (y - YOFF) * MM, z * MM)


def ceiling_samples(poly_mm, step_mm=500.0, inset_mm=60.0):
    """Puntos de muestreo (x, y) dentro de un polígono plano dado en mm."""
    from shapely.geometry import Point, Polygon
    pg = Polygon([(p[0], p[1]) for p in poly_mm]).buffer(-inset_mm)
    if pg.is_empty:
        pg = Polygon([(p[0], p[1]) for p in poly_mm])
    x0, y0, x1, y1 = pg.bounds
    pts = []
    x = x0
    while x <= x1 + 1e-6:
        y = y0
        while y <= y1 + 1e-6:
            if pg.contains(Point(x, y)):
                pts.append((x, y))
            y += step_mm
        x += step_mm
    # el mínimo bajo cubierta inclinada está en el borde: muestrear también el contorno
    ring = pg.exterior
    n = max(int(ring.length // 250.0), 4)
    for i in range(n):
        q = ring.interpolate(ring.length * i / n)
        pts.append((q.x, q.y))
    c = pg.representative_point()
    pts.append((c.x, c.y))
    return pts


def ceiling_z_at(x, y, floor_z, solids, top=12000.0):
    """Cota (mm) de la cara inferior más baja sobre floor_z en la vertical (x, y)."""
    seg = Part.makeLine(V(x, y, floor_z + 20.0), V(x, y, floor_z + top))
    best = None
    for s in solids:
        try:
            com = s.common(seg)
        except Exception:
            continue
        if not com.Edges:
            continue
        z = min(e.BoundBox.ZMin for e in com.Edges)
        if best is None or z < best:
            best = z
    return best


def clear_height_range(poly_mm, floor_z, solids):
    """(min, max, n_muestras) de altura libre en mm; (None, None, 0) si no hay cielo."""
    zs = []
    for x, y in ceiling_samples(poly_mm):
        z = ceiling_z_at(x, y, floor_z, solids)
        if z is not None:
            zs.append(z - floor_z)
    if not zs:
        return None, None, 0
    return min(zs), max(zs), len(zs)
