#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Renderiza vistas del modelo desde un .blend ya construido.

    RENDER_OUT=<dir> blender --background <modelo.blend> \
      --python tools/scripts/blender_render.py

Genera una vista aerea, dos perspectivas exteriores y una axonometrica.
Un render NO es una medicion: sirve para mirar el modelo, no para verificar
dimensiones. Para numeros, usar tools/scripts/json_to_extract.py.
"""
import math
import os
import sys

import bpy
from mathutils import Vector


def bbox_escena():
    xs, ys, zs = [], [], []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for v in obj.bound_box:
            p = obj.matrix_world @ Vector(v)
            xs.append(p.x); ys.append(p.y); zs.append(p.z)
    if not xs:
        return (0, 0, 0, 10, 10, 5)
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def apuntar(cam, objetivo):
    d = objetivo - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render(cam, path, ancho=1920, alto=1080):
    escena = bpy.context.scene
    escena.camera = cam
    escena.render.resolution_x = ancho
    escena.render.resolution_y = alto
    escena.render.filepath = os.path.abspath(path)
    escena.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("  render: %s" % path)


def main():
    out = os.environ.get("RENDER_OUT", ".")
    os.makedirs(out, exist_ok=True)

    x0, y0, z0, x1, y1, z1 = bbox_escena()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # La casa, sin contar el terreno que es mucho mayor.
    casa = Vector((cx, cy, min(z1, 8.0) / 2))
    diag = max(x1 - x0, y1 - y0)

    escena = bpy.context.scene
    escena.render.film_transparent = False

    cam_data = bpy.data.cameras.new("CamRender")
    cam_data.lens = 35
    cam = bpy.data.objects.new("CamRender", cam_data)
    escena.collection.objects.link(cam)

    vistas = [
        ("01_aerea_nororiente", Vector((18.0, -14.0, 20.0)), 35),
        ("02_exterior_norponiente", Vector((-12.0, -12.0, 6.0)), 28),
        ("03_exterior_suroriente", Vector((20.0, 22.0, 7.0)), 28),
    ]
    for nombre, pos, lente in vistas:
        cam.location = pos
        cam.data.lens = lente
        cam.data.type = "PERSP"
        apuntar(cam, casa)
        render(cam, os.path.join(out, "%s.png" % nombre))

    # axonometrica: camara ortografica a 45 grados
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = diag * 1.15
    cam.location = Vector((cx + diag, cy - diag, diag))
    apuntar(cam, casa)
    render(cam, os.path.join(out, "04_axonometrica.png"), 1600, 1600)

    return 0


if __name__ == "__main__":
    main()
