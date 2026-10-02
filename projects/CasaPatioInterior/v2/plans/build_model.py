# -*- coding: utf-8 -*-
"""Construye el modelo FreeCAD (objetos Arch) de la vivienda, v2.

    V2_DIR=projects/CasaPatioInterior/v2 \
    BUILD_OUT=projects/CasaPatioInterior/v2/plans/casa_v2.FCStd \
      "E:/FreeCAD/bin/freecadcmd.exe" projects/CasaPatioInterior/v2/plans/build_model.py

Fuentes (no se modifican):
  ../../plans/casa_rev_h.json   muros, vanos, losas, cubiertas, escalera, mobiliario (v0)
  recintos_v2.json              polígonos de recinto derivados y verificados contra el
                                documento rev. G (derive_recintos.py)

Marco de coordenadas del modelo (mm): X este, Y norte, Z arriba, origen en la esquina
NO de la envolvente a nivel NPT. Es dextrógiro; la convención del repo (+Y sur) es
levógira y no se puede representar en FreeCAD sin espejar el edificio. Ver README.

Termina con código != 0 si alguna autocomprobación geométrica falla.
"""
import json
import math
import os
import sys

import FreeCAD
import Part
import Draft
import Arch
from FreeCAD import Vector as V, Placement, Rotation

V2 = os.environ.get("V2_DIR")
OUT = os.environ.get("BUILD_OUT")
if not V2 or not OUT:
    raise SystemExit("falta V2_DIR o BUILD_OUT en el entorno")
sys.path.insert(0, os.path.join(V2, "plans"))
import v2lib                                            # noqa: E402
from v2lib import MM, YOFF, P                           # noqa: E402

SPEC = json.load(open(os.path.join(V2, "..", "plans", "casa_rev_h.json"), encoding="utf-8"))
REC = json.load(open(os.path.join(V2, "plans", "recintos_v2.json"), encoding="utf-8"))

doc = FreeCAD.newDocument("CasaPatioInterior_v2")
LV = {l["id"]: l["z"] for l in SPEC["levels"]}
problems = []


def comp(shape, label, ifc, mat=None):
    """Envuelve una forma Part en un objeto Arch (Component) con IfcType."""
    holder = doc.addObject("Part::Feature", label + "_base")
    holder.Shape = shape
    obj = Arch.makeComponent(holder, name=label)
    obj.Label = label
    try:
        obj.IfcType = ifc
    except Exception as e:                              # enumeración distinta en otra versión
        problems.append("IfcType %r no aceptado en %s: %s" % (ifc, label, e))
    if hasattr(holder, "ViewObject") and holder.ViewObject:
        holder.ViewObject.Visibility = False
    return obj


def extrude_xz(poly, y0, y1):
    """Prisma: polígono (x, z) en m extruido a lo largo de Y (m del documento)."""
    pts = [P(x, y0, z) for x, z in poly]
    w = Part.makePolygon(pts + [pts[0]])
    return Part.Face(w).extrude(V(0, (y1 - y0) * MM, 0))


def prism_xy(poly, z0, z1):
    pts = [P(x, y, z0) for x, y in poly]
    w = Part.makePolygon(pts + [pts[0]])
    return Part.Face(w).extrude(V(0, 0, (z1 - z0) * MM))


# ------------------------------------------------------------------ muros
def wall_frame(w):
    (ax, ay), (bx, by) = w["a"], w["b"]
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    o0, o1 = (0.0, w["t"]) if w.get("align", "center") == "left" else (-w["t"] / 2, w["t"] / 2)
    return ax, ay, ux, uy, nx, ny, L, o0, o1


def opening_on_wall(fr, rect, tol=0.02):
    ax, ay, ux, uy, nx, ny, L, o0, o1 = fr
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    d = (cx - ax) * nx + (cy - ay) * ny
    if not (min(o0, o1) - tol <= d <= max(o0, o1) + tol):
        return None
    sa = (x0 - ax) * ux + (y0 - ay) * uy
    sb = (x1 - ax) * ux + (y1 - ay) * uy
    sa, sb = min(sa, sb), max(sa, sb)
    if sb - sa < 0.25 or sb < -tol or sa > L + tol:
        return None
    return max(sa, 0.0), min(sb, L)


walls = []
for w in SPEC["walls"]:
    z0 = LV[w["level"]]
    ax, ay, ux, uy, nx, ny, L, o0, o1 = fr = wall_frame(w)
    base = Draft.makeLine(P(*w["a"], z0), P(*w["b"], z0))
    # El "Left" de Arch es el lado opuesto al "left" del JSON (verificado por bbox).
    align = "Right" if w.get("align", "center") == "left" else "Center"
    wall = Arch.makeWall(base, width=w["t"] * MM, height=(w["top"] - z0) * MM, align=align)
    wall.Label = "Muro %s %02d" % (w["level"], len(walls) + 1)
    wall.IfcType = "Wall"
    walls.append({"obj": wall, "w": w, "fr": fr, "z0": z0, "ops": []})

doc.recompute()

# geometría esperada de cada muro vs construida
for e in walls:
    ax, ay, ux, uy, nx, ny, L, o0, o1 = e["fr"]
    xs = [ax + ux * s + nx * o for s in (0, L) for o in (o0, o1)]
    ys = [ay + uy * s + ny * o for s in (0, L) for o in (o0, o1)]
    bb = e["obj"].Shape.BoundBox
    got = (bb.XMin / MM, bb.XMax / MM, bb.YMin / MM + YOFF, bb.YMax / MM + YOFF)
    exp = (min(xs), max(xs), min(ys), max(ys))
    if max(abs(g - x) for g, x in zip(got, exp)) > 0.002:
        problems.append("%s: huella %s != esperada %s" % (e["obj"].Label, [round(v, 3) for v in got],
                                                           [round(v, 3) for v in exp]))

# ------------------------------------------------------------------ vanos
PRESET = {"window": "Fixed", "door": "Simple door", "open": "Opening only"}
counters = {}
openings_log = []
for o in SPEC["openings"]:
    host = None
    for e in walls:
        if e["w"]["level"] != o["level"]:
            continue
        hit = opening_on_wall(e["fr"], o["rect"])
        if hit:
            host, s0, s1 = e, hit[0], hit[1]
            break
    if host is None:
        problems.append("vano sin muro: %s %s" % (o["level"], o["rect"]))
        continue
    z0 = host["z0"]
    top = host["w"]["top"]
    h0, h1 = o.get("sill", 0.95), min(o.get("head", 2.2), top - z0)
    ax, ay, ux, uy, nx, ny, L, o0, o1 = host["fr"]
    kind = o["kind"]
    code = {"window": "V", "door": "P", "open": "H"}[kind]
    counters[(o["level"], code)] = counters.get((o["level"], code), 0) + 1
    label = "%s%02d-%s" % (code, counters[(o["level"], code)], o["level"])
    width, height = (s1 - s0) * MM, (h1 - h0) * MM
    theta = math.degrees(math.atan2(uy, ux))
    mid = (o0 + o1) / 2.0                               # centro del espesor del muro
    org = P(ax + ux * s0 + nx * mid, ay + uy * s0 + ny * mid, z0 + h0)
    pl = Placement(org, Rotation(V(0, 0, 1), theta)).multiply(Placement(V(0, 0, 0), Rotation(V(1, 0, 0), 90)))
    if kind == "open":
        # paso sin hoja: ventana Arch sin partes; corta el muro y no aporta forma
        rect = Draft.makeRectangle(width, height, placement=pl, face=True)
        win = Arch.makeWindow(rect)
        win.WindowParts = []
        win.IfcType = "Opening Element"
    else:
        win = Arch.makeWindowPreset(PRESET[kind], width=width, height=height,
                                    h1=50, h2=50, h3=50, w1=100, w2=50, o1=0, o2=50, placement=pl)
        win.IfcType = "Door" if kind == "door" else "Window"
    win.Label = label
    win.Hosts = [host["obj"]]
    host["ops"].append((s0, s1, h0, h1))
    openings_log.append((label, kind, host["obj"].Label, s0, s1, h0, h1))

doc.recompute()

# El marco debe quedar centrado en el espesor del muro; se corrige por el bbox real.
for lab, kind, wlab, s0, s1, h0, h1 in openings_log:
    win = doc.getObjectsByLabel(lab)[0]
    if win.Shape.isNull():
        continue
    host = [e for e in walls if e["obj"].Label == wlab][0]
    ax, ay, ux, uy, nx, ny, L, o0, o1 = host["fr"]
    bb = win.Shape.BoundBox
    cx, cy = bb.Center.x / MM, bb.Center.y / MM + YOFF
    d = (cx - ax) * nx + (cy - ay) * ny - (o0 + o1) / 2.0
    if abs(d) > 0.001:
        win.Placement = Placement(win.Placement.Base - V(nx * d * MM, ny * d * MM, 0), win.Placement.Rotation)
doc.recompute()

# volumen de cada muro = L*t*H - suma de vanos*t (sin traslape entre vanos)
for e in walls:
    ax, ay, ux, uy, nx, ny, L, o0, o1 = e["fr"]
    t = e["w"]["t"]
    H = e["w"]["top"] - e["z0"]
    exp = L * t * H - sum((s1 - s0) * (h1 - h0) * t for s0, s1, h0, h1 in e["ops"])
    got = e["obj"].Shape.Volume / MM ** 3
    if abs(got - exp) > 0.01 * exp:
        problems.append("%s: volumen %.3f m3 != esperado %.3f m3 (%d vanos)"
                        % (e["obj"].Label, got, exp, len(e["ops"])))

# ------------------------------------------------------------------ losas
from shapely.geometry import box as sbox                # noqa: E402
from shapely.ops import unary_union                     # noqa: E402


def polygon_to_face(pg, z_mm):
    def wire(coords):
        pts = [V(x * MM, (y - YOFF) * MM, z_mm) for x, y in coords]
        return Part.makePolygon(pts)
    outer = wire(list(pg.exterior.coords))
    f = Part.Face(outer)
    for ring in pg.interiors:
        f = Part.Face([outer, wire(list(ring.coords))])
    return f


slab_objs = {}
for s in SPEC["slabs"]:
    lvl = [k for k, z in LV.items() if abs(z - s["z"]) < 1e-6][0]
    u = unary_union([sbox(*r) for r in s["rects"]])
    geoms = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
    solids = []
    for g in geoms:
        face = polygon_to_face(g, (s["z"] - s["t"]) * MM)
        solids.append(face.extrude(V(0, 0, s["t"] * MM)))
    shape = solids[0] if len(solids) == 1 else Part.makeCompound(solids)
    holder = doc.addObject("Part::Feature", "Losa_%s_base" % lvl)
    holder.Shape = shape
    slab = Arch.makeComponent(holder, name="Losa %s" % lvl)
    slab.Label = "Losa %s (z=%.2f, e=%.2f)" % (lvl, s["z"], s["t"])
    slab.IfcType = "Slab"
    slab_objs[lvl] = slab

# --------------------------------------------------------------- hastiales
for i, gb in enumerate(SPEC["gables"]):
    y0 = gb["at"]
    y1 = y0 + gb["dir"] * gb["t"]
    comp(extrude_xz(gb["profile"], min(y0, y1), max(y0, y1)), "Hastial %d" % (i + 1), "Wall")

# ---------------------------------------------------------------- cubiertas
roof_shapes = []


def gable_z(x, r):
    a, b = r["x_ref"]
    rx, ez, rz = r["ridge_x"], r["eave_z"], r["ridge_z"]
    return ez + (x - a) / (rx - a) * (rz - ez) if x <= rx else ez + (b - x) / (b - rx) * (rz - ez)


for r_i, r in enumerate(SPEC["roofs"]):
    t = r.get("t", 0.2)
    solids = []
    if r["type"] == "gable":
        for y0, y1, x0, x1 in r["bands"]:
            rx = r["ridge_x"]
            xs = [x0] + ([rx] if x0 < rx < x1 else []) + [x1]
            for xa, xb in zip(xs[:-1], xs[1:]):
                za, zb = gable_z(xa, r), gable_z(xb, r)
                solids.append(extrude_xz([(xa, za), (xb, zb), (xb, zb - t), (xa, za - t)], y0, y1))
        label = "Cubierta dos aguas"
    else:
        (x0, z0), (x1, z1) = r["from"], r["to"]
        y0, y1 = r["y"]
        solids.append(extrude_xz([(x0, z0), (x1, z1), (x1, z1 - t), (x0, z0 - t)], y0, y1))
        label = "Cubierta ala oriente (una agua)"
    comp_shape = Part.makeCompound(solids)
    obj = comp(comp_shape, label, "Roof")
    roof_shapes.append(comp_shape)

# ------------------------------------------------------------ escalera
st = SPEC["stairs"][0]
ch, hu = st["riser"], st["tread"]
f1, f2 = st["flights"]
z_base = st["base"]


def stair_flight(n_steps, x_w, y_start, d, z0, label):
    """Tramo recto Arch: n_steps alzadas, n_steps-1 huellas visibles."""
    run = (n_steps - 1) * hu * MM
    stairs = Arch.makeStairs(length=run, width=(x_w[1] - x_w[0]) * MM,
                             height=n_steps * ch * MM, steps=n_steps)
    stairs.Label = label
    # Arch corre el tramo hacia +X y su ancho hacia -Y local.
    if d < 0:       # sube hacia -Y: X->-Y, ancho -> -X, origen en x máximo
        pl = Placement(P(x_w[1], y_start, z0), Rotation(V(0, 0, 1), -90))
    else:           # sube hacia +Y: X->+Y, ancho -> +X, origen en x mínimo
        pl = Placement(P(x_w[0], y_start, z0), Rotation(V(0, 0, 1), 90))
    stairs.Placement = pl
    return stairs


s1 = stair_flight(f1["steps"] + 1, f1["x"], f1["y_start"], f1["dir"], z_base, "Escalera Tramo 1")
n_land = f1["steps"] + 1                         # alzadas hasta la cara del descanso
lx0, ly0, lx1, ly1 = f1["landing"]
landing = comp(prism_xy([(lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1)], z_base, z_base + n_land * ch),
               "Escalera Descanso", "Stair Flight")
s2 = stair_flight(f2["steps"], f2["x"], f2["y_start"], f2["dir"], z_base + n_land * ch, "Escalera Tramo 2")
# peldaño de llegada: el JSON lo declara como último escalón a nivel de piso
ya = f2["y_start"] + (f2["steps"] - 1) * hu
arrival = comp(prism_xy([(f2["x"][0], ya), (f2["x"][1], ya), (f2["x"][1], ya + hu), (f2["x"][0], ya + hu)],
                        z_base, z_base + (n_land + f2["steps"]) * ch),
               "Escalera Peldaño de llegada", "Stair Flight")
for s in (s1, s2):
    s.IfcType = "Stair"
    try:
        s.StructureThickness = 150
    except Exception:
        pass

# --------------------------------------------------- terreno, pavimento, mobiliario
g = SPEC["ground"]
gx0, gy0, gx1, gy1 = g["rect"]
comp(prism_xy([(gx0, gy0), (gx1, gy0), (gx1, gy1), (gx0, gy1)], g["z"] - 0.4, g["z"]),
     "Terreno (referencial)", "Building Element Proxy")
for pv in SPEC["paving"]:
    shp = [prism_xy([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], pv["z"] - 0.06, pv["z"])
           for x0, y0, x1, y1 in pv["rects"]]
    comp(Part.makeCompound(shp), "Pavimento exterior", "Covering")
for i, b in enumerate(SPEC["boxes"]):
    x0, x1 = b["x"]; y0, y1 = b["y"]; z0, z1 = b["z"]
    comp(prism_xy([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1),
         "Mobiliario %02d" % (i + 1), "Furniture")

doc.recompute()

# ------------------------------------------------------------------ recintos
ceiling_solids = {
    "p1": [slab_objs["p2"].Shape] + roof_shapes,
    "p2": roof_shapes,
}
space_log = []
for lv in ("p1", "p2"):
    floor_z = LV[lv] * MM
    for r in REC["niveles"][lv]["recintos"]:
        pts = [V(x * MM, (y - YOFF) * MM, floor_z) for x, y in r["neto"]]
        hmin, hmax, n = v2lib.clear_height_range([(p.x, p.y) for p in pts], floor_z, ceiling_solids[lv])
        exterior = r["tipo"] == "exterior"
        # Altura del Space = la MENOR altura libre medida bajo cielo (conservadora);
        # el máximo (bajo cumbrera) queda en space_log y lo reporta measure_v2.py.
        # Exteriores/descubiertos: 2,60 m referencial, no es una medición.
        height = hmin if (hmin and not exterior) else 2600.0
        solid = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, 0, height))
        holder = doc.addObject("Part::Feature", "Base %s %s" % (r["label"], lv))
        holder.Shape = solid
        sp = Arch.makeSpace(holder)
        sp.Label = r["label"]
        sp.Label2 = r["label"]       # FreeCAD renombra los repetidos (Escalera001); el original queda aquí
        sp.IfcType = "Space"
        sp.Description = "%s | nivel %s | tipo %s | delimitación %s" % (
            r["nombre_doc"], lv, r["tipo"], r["delimitacion"])
        space_log.append((lv, r["label"], hmin, hmax, n))
        if holder.ViewObject:
            holder.ViewObject.Visibility = False

doc.recompute()

# nombre único por nivel: los Space repetidos ("Escalera" en p1 y p2) conservan la etiqueta
# del documento; el nivel va en Description y en la posición Z de la forma.

# ------------------------------------------------------------ autocomprobación
n_walls = len([o for o in doc.Objects if getattr(o, "IfcType", "") == "Wall"])
if n_walls < len(SPEC["walls"]):
    problems.append("faltan muros: %d < %d" % (n_walls, len(SPEC["walls"])))
spaces = [o for o in doc.Objects if getattr(o, "IfcType", "") == "Space"]
expected_spaces = sum(len(REC["niveles"][l]["recintos"]) for l in ("p1", "p2"))
if len(spaces) != expected_spaces:
    problems.append("Space %d != %d" % (len(spaces), expected_spaces))
for o in doc.Objects:
    if hasattr(o, "Shape") and getattr(o, "IfcType", None) not in (None, "Opening Element")             and (o.Shape.isNull() or o.Shape.Volume < 1e-6):
        problems.append("forma vacía: " + o.Label)
    if hasattr(o, "isValid") and not o.isValid():
        problems.append("objeto inválido: " + o.Label)

doc.saveAs(OUT)
print("saved", OUT, "objects:", len(doc.Objects), "walls:", n_walls, "spaces:", len(spaces),
      "windows+doors:", len(openings_log))
for lv, label, hmin, hmax, n in space_log:
    print("  %s %-26s libre min %s max %s (%d muestras)" % (
        lv, label, "%.3f" % (hmin / 1000) if hmin else "-", "%.3f" % (hmax / 1000) if hmax else "-", n))
if problems:
    print("PROBLEMAS (%d):" % len(problems))
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("BUILD OK")
