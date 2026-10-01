#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construye el modelo 3D en Blender desde la especificacion JSON.

Se ejecuta DENTRO de Blender:

    BUILD_SPEC=<planta.json> BUILD_OUT=<salida.blend> \
      blender --background --python tools/scripts/blender_build.py

Las rutas van por variables de entorno porque Blender consume los argumentos
posicionales antes de pasarlos al script (se pueden pasar tras "--", pero el
entorno evita el problema por completo y es el patron que ya usa este repo).

Construye geometria parametrica real: cada muro es un solido extruido con su
espesor y alineacion, no un OBJ triangulado importado. Eso permite editar,
acotar y seccionar en Blender.

Convencion de ejes: el JSON trae planta (x, y) y cotas z.
Blender es Z-up, que coincide con la convencion del repositorio
(+X este, +Y sur, +Z arriba), asi que el mapeo es directo:
    JSON (x, y, z)  ->  Blender (x, y, z)
No se usa la conversion a Y-up de three.js.
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

# ------------------------------------------------------------------ utilidades

MATERIALES = {
    "muro":      (0.945, 0.937, 0.918, 1.0),
    "muro_int":  (0.898, 0.886, 0.867, 1.0),
    "cubierta":  (0.267, 0.286, 0.306, 1.0),
    "losa":      (0.855, 0.843, 0.812, 1.0),
    "vidrio":    (0.596, 0.749, 0.878, 0.35),
    "pavimento": (0.906, 0.886, 0.827, 1.0),
    "terreno":   (0.588, 0.647, 0.451, 1.0),
    "madera":    (0.780, 0.663, 0.514, 1.0),
    "mueble":    (0.741, 0.749, 0.757, 1.0),
}


def limpiar_escena():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for bloque in (bpy.data.meshes, bpy.data.materials, bpy.data.collections):
        for item in list(bloque):
            if item.users == 0:
                bloque.remove(item)


def material(nombre):
    if nombre in bpy.data.materials:
        return bpy.data.materials[nombre]
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    r, g, b, a = MATERIALES.get(nombre, (0.8, 0.8, 0.8, 1.0))
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
        if a < 1.0:
            bsdf.inputs["Alpha"].default_value = a
            mat.blend_method = "BLEND"
        # Roughness varia por material para que el render no sea plano.
        rug = 0.15 if nombre == "vidrio" else 0.75
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = rug
    return mat


def coleccion(nombre):
    if nombre in bpy.data.collections:
        return bpy.data.collections[nombre]
    col = bpy.data.collections.new(nombre)
    bpy.context.scene.collection.children.link(col)
    return col


def caja(nombre, x0, y0, z0, x1, y1, z1, mat, col):
    """Solido rectangular por coordenadas opuestas."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    if min(x1 - x0, y1 - y0, z1 - z0) <= 1e-9:
        return None

    malla = bpy.data.meshes.new(nombre)
    obj = bpy.data.objects.new(nombre, malla)
    col.objects.link(obj)

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(malla)
    bm.free()

    obj.scale = ((x1 - x0), (y1 - y0), (z1 - z0))
    obj.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    malla.materials.append(material(mat))
    return obj


def poligono_muro(w):
    """Rectangulo en planta del muro segun su alineacion."""
    (x1, y1), (x2, y2) = w["a"], w["b"]
    t = w["t"]
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    nx, ny = -dy / L, dx / L

    align = w.get("align", "center")
    if align == "center":
        o1, o2 = -t / 2.0, t / 2.0
    elif align == "left":
        o1, o2 = 0.0, t
    else:
        o1, o2 = -t, 0.0

    return [
        (x1 + nx * o1, y1 + ny * o1),
        (x2 + nx * o1, y2 + ny * o1),
        (x2 + nx * o2, y2 + ny * o2),
        (x1 + nx * o2, y1 + ny * o2),
    ]


def muro_solido(nombre, poly, z0, z1, mat, col):
    """Extruye el poligono en planta entre dos cotas."""
    malla = bpy.data.meshes.new(nombre)
    obj = bpy.data.objects.new(nombre, malla)
    col.objects.link(obj)

    bm = bmesh.new()
    verts = [bm.verts.new((x, y, z0)) for x, y in poly]
    cara = bm.faces.new(verts)
    bmesh.ops.translate(bm, vec=Vector((0, 0, 0)), verts=verts)
    r = bmesh.ops.extrude_face_region(bm, geom=[cara])
    nuevos = [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=Vector((0, 0, z1 - z0)), verts=nuevos)
    bm.normal_update()
    bm.to_mesh(malla)
    bm.free()

    malla.materials.append(material(mat))
    return obj


def booleano_restar(objetivo, herramientas):
    """Resta solidos del objetivo y elimina las herramientas."""
    for i, h in enumerate(herramientas):
        mod = objetivo.modifiers.new("vano_%d" % i, "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = h
        mod.solver = "EXACT"
    bpy.context.view_layer.objects.active = objetivo
    for mod in list(objetivo.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except RuntimeError as exc:
            print("  aviso: no se pudo aplicar %s (%s)" % (mod.name, exc))
    for h in herramientas:
        bpy.data.objects.remove(h, do_unlink=True)


# ------------------------------------------------------------------ construccion

def construir(spec):
    niveles = {l["id"]: l["z"] for l in spec["levels"]}

    col_muros = coleccion("Muros")
    col_losas = coleccion("Losas")
    col_vanos = coleccion("Vanos")
    col_esc = coleccion("Escalera")
    col_cub = coleccion("Cubierta")
    col_sitio = coleccion("Sitio")
    col_mob = coleccion("Mobiliario")

    # --- terreno y pavimentos
    g = spec.get("ground")
    if g and "rect" in g:
        x0, y0, x1, y1 = g["rect"]
        caja("Terreno", x0, y0, g.get("z", -0.55), x1, y1, g.get("z", -0.55) + 0.4,
             "terreno", col_sitio)
    for i, p in enumerate(spec.get("paving", [])):
        z = p.get("z", -0.02)
        for j, (x0, y0, x1, y1) in enumerate(p.get("rects", [])):
            caja("Pavimento_%d_%d" % (i, j), x0, y0, z - 0.06, x1, y1, z,
                 p.get("material", "pavimento"), col_sitio)

    # --- losas
    for s in spec.get("slabs", []):
        for i, (x0, y0, x1, y1) in enumerate(s["rects"]):
            caja("Losa_%.2f_%d" % (s["z"], i), x0, y0, s["z"] - s["t"], x1, y1, s["z"],
                 s.get("material", "losa"), col_losas)

    # --- muros con sus vanos restados
    n_muros = n_vanos = 0
    for idx, w in enumerate(spec["walls"]):
        poly = poligono_muro(w)
        if not poly:
            continue
        z0 = niveles[w["level"]]
        z1 = w["top"]
        obj = muro_solido("Muro_%03d" % idx, poly, z0, z1, "muro", col_muros)
        n_muros += 1

        # vanos que caen dentro de este muro
        herramientas = []
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        mx0, mx1 = min(xs), max(xs)
        my0, my1 = min(ys), max(ys)
        for o in spec.get("openings", []):
            if o["level"] != w["level"]:
                continue
            ox0, oy0, ox1, oy1 = o["rect"]
            # solape en planta con el muro
            if min(ox1, mx1) - max(ox0, mx0) <= 1e-6:
                continue
            if min(oy1, my1) - max(oy0, my0) <= 1e-6:
                continue
            sill = o.get("sill", 0.0) or 0.0
            head = o.get("head", z1 - z0) or (z1 - z0)
            h = caja("corte", ox0 - 0.01, oy0 - 0.01, z0 + sill,
                     ox1 + 0.01, oy1 + 0.01, z0 + head, "muro", col_vanos)
            if h:
                herramientas.append(h)
        if herramientas:
            booleano_restar(obj, herramientas)
            n_vanos += len(herramientas)

    # --- vidrios en las ventanas
    for i, o in enumerate(spec.get("openings", [])):
        if o["kind"] != "window":
            continue
        z = niveles[o["level"]]
        x0, y0, x1, y1 = o["rect"]
        sill = o.get("sill", 0.0) or 0.0
        head = o.get("head", 2.2) or 2.2
        # lamina delgada centrada en el espesor del vano
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if (x1 - x0) > (y1 - y0):
            caja("Vidrio_%03d" % i, x0, cy - 0.006, z + sill, x1, cy + 0.006, z + head,
                 "vidrio", col_vanos)
        else:
            caja("Vidrio_%03d" % i, cx - 0.006, y0, z + sill, cx + 0.006, y1, z + head,
                 "vidrio", col_vanos)

    # --- escalera (mismo conteo que build3d: cada descanso suma una alzada)
    n_pasos = 0
    for st in spec.get("stairs", []):
        z = st["base"]
        ch, hu = st["riser"], st["tread"]
        n = 0
        for fl in st["flights"]:
            x0, x1 = fl["x"]
            y = fl["y_start"]
            d = fl["dir"]
            for k in range(1, fl["steps"] + 1):
                n += 1
                ya = y + d * (k - 1) * hu
                yb = y + d * k * hu
                caja("Peldano_%02d" % n, x0, min(ya, yb), z, x1, max(ya, yb),
                     z + n * ch, "madera", col_esc)
                n_pasos += 1
            if fl.get("landing"):
                lx0, ly0, lx1, ly1 = fl["landing"]
                n += 1
                caja("Descanso_%02d" % n, lx0, ly0, z, lx1, ly1, z + n * ch,
                     "madera", col_esc)
        print("  escalera: %d alzadas, llega a %.4f m" % (n, n * ch))

    # --- hastiales (perfil en un plano, extruido segun su espesor)
    for i, gb in enumerate(spec.get("gables", [])):
        construir_hastial(gb, i, col_muros)

    # --- cubiertas
    for i, r in enumerate(spec.get("roofs", [])):
        construir_cubierta(r, i, col_cub)

    # --- mobiliario
    for i, b in enumerate(spec.get("boxes", [])):
        caja("Mueble_%02d" % i, b["x"][0], b["y"][0], b["z"][0],
             b["x"][1], b["y"][1], b["z"][1], b.get("material", "mueble"), col_mob)

    print("  muros: %d  vanos restados: %d  peldanos: %d" % (n_muros, n_vanos, n_pasos))


def construir_hastial(gb, idx, col):
    """Perfil poligonal en el plano x o y, extruido segun su espesor.

    'plane' indica el plano donde vive el perfil, 'at' su posicion, 'dir' hacia
    que lado se extruye y 'profile' los pares (coordenada en planta, cota).
    """
    perfil = gb.get("profile", [])
    if len(perfil) < 3:
        return
    t = gb.get("t", 0.2)
    at = gb["at"]
    d = gb.get("dir", 1)

    malla = bpy.data.meshes.new("Hastial_%02d" % idx)
    obj = bpy.data.objects.new(malla.name, malla)
    col.objects.link(obj)

    bm = bmesh.new()
    if gb.get("plane") == "y":
        pts = [(u, at, z) for u, z in perfil]
        desp = Vector((0, t * d, 0))
    else:
        pts = [(at, u, z) for u, z in perfil]
        desp = Vector((t * d, 0, 0))

    verts = [bm.verts.new(p) for p in pts]
    try:
        cara = bm.faces.new(verts)
    except ValueError:
        bm.free()
        print("  aviso: hastial %d con perfil invalido" % idx)
        return
    res = bmesh.ops.extrude_face_region(bm, geom=[cara])
    nuevos = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=desp, verts=nuevos)
    bm.normal_update()
    bm.to_mesh(malla)
    bm.free()
    malla.materials.append(material(gb.get("material", "muro")))


def construir_cubierta(r, idx, col):
    """Faldones a dos aguas o de una caida, como solidos inclinados."""
    tipo = r.get("type")
    t = r.get("t", 0.22)

    if tipo == "gable":
        rx = r["ridge_x"]
        ez, rz = r["eave_z"], r["ridge_z"]
        for j, banda in enumerate(r.get("bands", [])):
            y0, y1, x0, x1 = banda
            for lado, (xa, xb) in enumerate(((x0, rx), (rx, x1))):
                if xb - xa <= 1e-6:
                    continue
                malla = bpy.data.meshes.new("Faldon_%d_%d_%d" % (idx, j, lado))
                obj = bpy.data.objects.new(malla.name, malla)
                col.objects.link(obj)
                za = rz if abs(xa - rx) < 1e-6 else ez
                zb = rz if abs(xb - rx) < 1e-6 else ez
                bm = bmesh.new()
                base = [bm.verts.new(p) for p in
                        ((xa, y0, za), (xb, y0, zb), (xb, y1, zb), (xa, y1, za))]
                cara = bm.faces.new(base)
                res = bmesh.ops.extrude_face_region(bm, geom=[cara])
                nuevos = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
                bmesh.ops.translate(bm, vec=Vector((0, 0, t)), verts=nuevos)
                bm.normal_update()
                bm.to_mesh(malla)
                bm.free()
                malla.materials.append(material("cubierta"))

    elif tipo == "shed":
        (x0, z0), (x1, z1) = r["from"], r["to"]
        y0, y1 = r["y"]
        malla = bpy.data.meshes.new("Faldon_shed_%d" % idx)
        obj = bpy.data.objects.new(malla.name, malla)
        col.objects.link(obj)
        bm = bmesh.new()
        base = [bm.verts.new(p) for p in
                ((x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0))]
        cara = bm.faces.new(base)
        res = bmesh.ops.extrude_face_region(bm, geom=[cara])
        nuevos = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=Vector((0, 0, t)), verts=nuevos)
        bm.normal_update()
        bm.to_mesh(malla)
        bm.free()
        malla.materials.append(material("cubierta"))


def montar_escena(spec):
    """Sol, camara y ajustes de render."""
    escena = bpy.context.scene
    escena.unit_settings.system = "METRIC"
    escena.unit_settings.length_unit = "METERS"

    bx0, by0, bx1, by1 = spec["bbox"]
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2

    sol = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", "SUN"))
    bpy.context.scene.collection.objects.link(sol)
    sol.data.energy = 3.5
    sol.data.angle = math.radians(1.0)
    # Sol del norte: en el hemisferio sur la fachada norte es la asoleada.
    sol.rotation_euler = (math.radians(52), 0, math.radians(200))

    cam_data = bpy.data.cameras.new("Camara")
    cam_data.lens = 28
    cam = bpy.data.objects.new("Camara", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (bx1 + 16, by0 - 16, 13)
    objetivo = Vector((cx, cy, 3.0))
    direccion = objetivo - cam.location
    cam.rotation_euler = direccion.to_track_quat("-Z", "Y").to_euler()
    escena.camera = cam

    # El identificador de EEVEE cambio entre versiones (EEVEE / EEVEE_NEXT).
    # Se elige el que exista en esta build en vez de fijar uno a ciegas.
    motores = escena.render.bl_rna.properties["engine"].enum_items.keys()
    for candidato in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        if candidato in motores:
            escena.render.engine = candidato
            break
    escena.render.resolution_x = 1920
    escena.render.resolution_y = 1080
    escena.render.film_transparent = False
    if escena.world is None:
        escena.world = bpy.data.worlds.new("World")
    escena.world.use_nodes = True
    fondo = escena.world.node_tree.nodes.get("Background")
    if fondo:
        fondo.inputs[0].default_value = (0.72, 0.80, 0.90, 1.0)
        fondo.inputs[1].default_value = 1.0


def main():
    spec_path = os.environ.get("BUILD_SPEC")
    out_path = os.environ.get("BUILD_OUT")
    if not spec_path:
        print("error: definir BUILD_SPEC (y opcionalmente BUILD_OUT)", file=sys.stderr)
        return 2

    spec = json.load(open(spec_path, encoding="utf-8"))
    print("construyendo: %s" % spec.get("meta", {}).get("titulo", spec_path))

    limpiar_escena()
    construir(spec)
    montar_escena(spec)

    if out_path:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_path))
        print("guardado: %s" % out_path)

    total = len([o for o in bpy.data.objects if o.type == "MESH"])
    print("objetos de malla: %d" % total)
    return 0


if __name__ == "__main__":
    main()
