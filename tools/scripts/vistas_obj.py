# -*- coding: utf-8 -*-
"""Vistas 3D de control de un OBJ: aérea desde el noreste y desde el suroeste.

Se ejecuta DENTRO de Blender (rutas por variables de entorno, como el resto de los
scripts de Blender del repositorio):

    VISTAS_OBJ=<modelo.obj> VISTAS_OUT=<carpeta> [VISTAS_MOTOR=CYCLES] \
      blender --background --python tools/scripts/vistas_obj.py

Escribe <carpeta>/3d_noreste.png y <carpeta>/3d_suroeste.png. Cámara ortográfica
sobre el centro del modelo. Supone el OBJ con Y arriba y el norte hacia -Z del OBJ
(lo que escribe versions/vN/scripts/export_obj.py): al importarlo, el norte queda hacia +Y.

Motor: CYCLES por defecto (funciona sin GPU, también en un servidor). Con GPU,
VISTAS_MOTOR=BLENDER_WORKBENCH es mucho más rápido.

Una vista NO es una medición: para eso, tools/scripts/verificar_modelo3d.py.
"""
import math
import os

import bpy
from mathutils import Vector


def main():
    obj_path = os.environ["VISTAS_OBJ"]
    out = os.environ["VISTAS_OUT"]
    motor = os.environ.get("VISTAS_MOTOR", "CYCLES")
    os.makedirs(out, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    # un objeto por grupo "g" del OBJ (muro, cubierta, terreno...): así el encuadre puede
    # dejar fuera el terreno y el pavimento exterior
    bpy.ops.wm.obj_import(filepath=obj_path, use_split_objects=True, use_split_groups=True)
    sc = bpy.context.scene
    sc.render.engine = motor
    if motor == "CYCLES":
        sc.cycles.device = "CPU"
        sc.cycles.samples = 32
    sc.render.resolution_x, sc.render.resolution_y = 1100, 760

    mundo = bpy.data.worlds.new("Mundo")
    sc.world = mundo
    mundo.use_nodes = True
    fondo = mundo.node_tree.nodes["Background"]
    fondo.inputs[0].default_value = (0.85, 0.88, 0.92, 1.0)
    fondo.inputs[1].default_value = 0.8
    sol = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", "SUN"))
    sc.collection.objects.link(sol)
    sol.data.energy = 3.0
    sol.rotation_euler = (math.radians(50), 0, math.radians(30))

    # centro y tamaño de la casa: sin terreno ni pavimento exterior, que son mucho mayores
    pts = []
    for o in bpy.data.objects:
        nombre = o.name.lower()
        if o.type == "MESH" and "terreno" not in nombre and "pavimento" not in nombre:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    centro = (lo + hi) / 2
    lado = max(hi.x - lo.x, hi.y - lo.y)

    cam = bpy.data.objects.new("Camara", bpy.data.cameras.new("Camara"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = lado * 1.55
    d = lado * 1.6
    for nombre, (sx, sy) in (("3d_noreste", (1, 1)), ("3d_suroeste", (-1, -1))):
        cam.location = centro + Vector((sx * d * 0.9, sy * d, d * 0.95))
        cam.rotation_euler = (centro - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(out, nombre + ".png")
        bpy.ops.render.render(write_still=True)
        print("vista:", sc.render.filepath)


if __name__ in ("__main__", "<run_path>"):
    main()
