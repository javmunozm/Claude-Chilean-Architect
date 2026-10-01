#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build3d.py — convierte una especificación de planta (JSON) en un modelo 3D.

Salidas:
  <out>.obj / <out>.mtl   modelo para Blender, SketchUp, Rhino, visor de Windows
  <out>.html              visor web interactivo autocontenido

Convención de ejes:
  planta (x, y) en metros  ->  mundo (x, z_altura, y)
  el eje Y del mundo es la altura (convención de three.js)

Uso:
  python3 build3d.py planta.json --out modelo
"""
import json
import math
import os
import sys

# --------------------------------------------------------------------- malla
class Mesh:
    def __init__(self):
        self.groups = {}          # material -> lista plana de coordenadas

    def tri(self, mat, a, b, c):
        g = self.groups.setdefault(mat, [])
        g.extend([a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2]])

    def quad(self, mat, a, b, c, d):
        self.tri(mat, a, b, c)
        self.tri(mat, a, c, d)

    def box(self, mat, x0, y0, z0, x1, y1, z1):
        """Caja alineada a los ejes en coordenadas de mundo (y = altura)."""
        if x1 - x0 <= 1e-6 or y1 - y0 <= 1e-6 or z1 - z0 <= 1e-6:
            return
        p = [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
             (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
        for a, b, c, d in f:
            self.quad(mat, p[a], p[b], p[c], p[d])

    def prism(self, mat, poly, axis, at, t, sign=1):
        """Prisma a partir de un polígono (u, v) extruido en el eje indicado.
        axis 'y' -> el polígono vive en (x, altura) y se extruye en y de planta."""
        n = len(poly)
        a0, a1 = at, at + sign * t
        lo, hi = min(a0, a1), max(a0, a1)

        def P(u, v, a):
            return (u, v, a) if axis == "y" else (a, v, u)

        for i in range(1, n - 1):
            for a, rev in ((lo, False), (hi, True)):
                tri = [P(poly[0][0], poly[0][1], a),
                       P(poly[i][0], poly[i][1], a),
                       P(poly[i + 1][0], poly[i + 1][1], a)]
                if rev:
                    tri.reverse()
                self.tri(mat, *tri)
        for i in range(n):
            u0, v0 = poly[i]
            u1, v1 = poly[(i + 1) % n]
            self.quad(mat, P(u0, v0, lo), P(u1, v1, lo),
                      P(u1, v1, hi), P(u0, v0, hi))


# ------------------------------------------------------------------- muros
def wall_rect(a, b, t, align):
    """Devuelve el rectángulo en planta que ocupa el muro y su eje longitudinal."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux                      # normal a la izquierda del recorrido
    off0, off1 = (0.0, t) if align == "left" else (-t / 2.0, t / 2.0)
    return (ax, ay, ux, uy, nx, ny, L, off0, off1)


def opening_on_wall(w, rect, tol=0.02):
    """Si el vano pertenece al muro, devuelve (s0, s1); si no, None."""
    ax, ay, ux, uy, nx, ny, L, o0, o1 = w
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    d = (cx - ax) * nx + (cy - ay) * ny            # distancia transversal
    if not (min(o0, o1) - tol <= d <= max(o0, o1) + tol):
        return None
    s_a = (x0 - ax) * ux + (y0 - ay) * uy
    s_b = (x1 - ax) * ux + (y1 - ay) * uy
    sa, sb = min(s_a, s_b), max(s_a, s_b)
    # el vano debe correr a lo largo del muro, no atravesarlo
    if sb - sa < 0.25:
        return None
    if sb < -tol or sa > L + tol:
        return None
    return max(sa, 0.0), min(sb, L)


def build_wall(mesh, w, z0, z1, openings, mat, mat_glass):
    ax, ay, ux, uy, nx, ny, L, o0, o1 = w

    def pt(s, off, z):
        return (ax + ux * s + nx * off, z, ay + uy * s + ny * off)

    def slab(s0, s1, h0, h1, m):
        if s1 - s0 < 1e-6 or h1 - h0 < 1e-6:
            return
        a = pt(s0, o0, h0); b = pt(s1, o0, h0)
        c = pt(s1, o1, h0); d = pt(s0, o1, h0)
        A = pt(s0, o0, h1); B = pt(s1, o0, h1)
        C = pt(s1, o1, h1); D = pt(s0, o1, h1)
        mesh.quad(m, a, b, c, d)          # inferior
        mesh.quad(m, A, D, C, B)          # superior
        mesh.quad(m, a, A, B, b)          # cara exterior
        mesh.quad(m, d, c, C, D)          # cara interior
        mesh.quad(m, a, d, D, A)          # jamba inicial
        mesh.quad(m, b, B, C, c)          # jamba final

    ops = sorted(openings, key=lambda o: o[0])
    cuts = [0.0]
    for s0, s1, h0, h1, kind in ops:
        cuts += [max(0.0, s0), min(L, s1)]
    cuts.append(L)
    cuts = sorted(set(round(c, 4) for c in cuts))

    for i in range(len(cuts) - 1):
        a, b = cuts[i], cuts[i + 1]
        if b - a < 1e-6:
            continue
        mid = (a + b) / 2.0
        here = None
        for o in ops:
            if o[0] - 1e-6 <= mid <= o[1] + 1e-6:
                here = o
                break
        if here is None:
            slab(a, b, z0, z1, mat)
        else:
            s0, s1, h0, h1, kind = here
            slab(a, b, z0, min(z0 + h0, z1), mat)          # antepecho
            slab(a, b, min(z0 + h1, z1), z1, mat)          # dintel
            if kind in ("window", "door"):
                gt = (o1 - o0) * 0.18
                gm = (o0 + o1) / 2.0
                ga, gb = gm - gt / 2.0, gm + gt / 2.0
                za, zb = z0 + h0, min(z0 + h1, z1)
                if kind == "door":
                    za = z0 + h0 + 0.02
                A = pt(a + 0.02, ga, za); B = pt(b - 0.02, ga, za)
                C = pt(b - 0.02, gb, za); D = pt(a + 0.02, gb, za)
                A2 = pt(a + 0.02, ga, zb); B2 = pt(b - 0.02, ga, zb)
                C2 = pt(b - 0.02, gb, zb); D2 = pt(a + 0.02, gb, zb)
                mesh.quad(mat_glass, A, A2, B2, B)
                mesh.quad(mat_glass, D, C, C2, D2)


# ----------------------------------------------------------------- cubiertas
def gable_z(x, r):
    a, b = r["x_ref"]
    rx, ez, rz = r["ridge_x"], r["eave_z"], r["ridge_z"]
    if x <= rx:
        return ez + (x - a) / (rx - a) * (rz - ez)
    return ez + (b - x) / (b - rx) * (rz - ez)


def build_roof(mesh, r, mat):
    t = r.get("t", 0.20)
    if r["type"] == "gable":
        for y0, y1, x0, x1 in r["bands"]:
            rx = r["ridge_x"]
            xs = [x0] + ([rx] if x0 < rx < x1 else []) + [x1]
            for i in range(len(xs) - 1):
                xa, xb = xs[i], xs[i + 1]
                za, zb = gable_z(xa, r), gable_z(xb, r)
                for dz in (0.0, -t):
                    A = (xa, za + dz, y0); B = (xb, zb + dz, y0)
                    C = (xb, zb + dz, y1); D = (xa, za + dz, y1)
                    if dz == 0.0:
                        mesh.quad(mat, A, D, C, B)
                    else:
                        mesh.quad(mat, A, B, C, D)
                mesh.quad(mat, (xa, za, y0), (xb, zb, y0),
                          (xb, zb - t, y0), (xa, za - t, y0))
                mesh.quad(mat, (xa, za, y1), (xa, za - t, y1),
                          (xb, zb - t, y1), (xb, zb, y1))
                for xe, ze in ((xa, za), (xb, zb)):
                    mesh.quad(mat, (xe, ze, y0), (xe, ze - t, y0),
                              (xe, ze - t, y1), (xe, ze, y1))
    else:                                    # shed / una sola caída
        x0, z0 = r["from"]
        x1, z1 = r["to"]
        y0, y1 = r["y"]
        for dz in (0.0, -t):
            A = (x0, z0 + dz, y0); B = (x1, z1 + dz, y0)
            C = (x1, z1 + dz, y1); D = (x0, z0 + dz, y1)
            if dz == 0.0:
                mesh.quad(mat, A, D, C, B)
            else:
                mesh.quad(mat, A, B, C, D)
        mesh.quad(mat, (x0, z0, y0), (x1, z1, y0), (x1, z1 - t, y0), (x0, z0 - t, y0))
        mesh.quad(mat, (x0, z0, y1), (x0, z0 - t, y1), (x1, z1 - t, y1), (x1, z1, y1))
        for xe, ze in ((x0, z0), (x1, z1)):
            mesh.quad(mat, (xe, ze, y0), (xe, ze - t, y0),
                      (xe, ze - t, y1), (xe, ze, y1))


# --------------------------------------------------------------------- build
def build(spec):
    m = Mesh()
    lv = {l["id"]: l for l in spec["levels"]}

    g = spec.get("ground")
    if g:
        x0, y0, x1, y1 = g["rect"]
        m.box("terreno", x0, g["z"] - 0.4, y0, x1, g["z"], y1)

    for pv in spec.get("paving", []):
        for x0, y0, x1, y1 in pv["rects"]:
            m.box(pv.get("material", "pavimento"), x0, pv["z"] - 0.06, y0,
                  x1, pv["z"], y1)

    for s in spec.get("slabs", []):
        for x0, y0, x1, y1 in s["rects"]:
            m.box(s.get("material", "losa"), x0, s["z"] - s["t"], y0, x1, s["z"], y1)

    ops_by_level = {}
    for o in spec.get("openings", []):
        ops_by_level.setdefault(o["level"], []).append(o)

    for w in spec["walls"]:
        L = lv[w["level"]]
        z0 = w.get("base", L["z"])
        z1 = w["top"]
        wr = wall_rect(w["a"], w["b"], w["t"], w.get("align", "center"))
        found = []
        for o in ops_by_level.get(w["level"], []):
            hit = opening_on_wall(wr, o["rect"])
            if hit:
                h0 = o.get("sill", 0.95)
                h1 = o.get("head", 2.20)
                if z0 + h1 > z1:
                    h1 = z1 - z0
                found.append((hit[0], hit[1], h0, h1, o["kind"]))
                o["_used"] = True
        build_wall(m, wr, z0, z1, found,
                   w.get("material", "muro"), "vidrio")

    for gb in spec.get("gables", []):
        m.prism(gb.get("material", "muro"), gb["profile"], gb["plane"],
                gb["at"], gb["t"], gb.get("dir", 1))

    for r in spec.get("roofs", []):
        build_roof(m, r, r.get("material", "cubierta"))

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
                ya, yb = (y + d * (k - 1) * hu, y + d * k * hu)
                m.box("madera", x0, z, min(ya, yb), x1, z + n * ch, max(ya, yb))
            if fl.get("landing"):
                lx0, ly0, lx1, ly1 = fl["landing"]
                n += 1
                m.box("madera", lx0, z, ly0, lx1, z + n * ch, ly1)

    for b in spec.get("boxes", []):
        m.box(b.get("material", "mueble"), b["x"][0], b["z"][0], b["y"][0],
              b["x"][1], b["z"][1], b["y"][1])

    unused = [o for o in spec.get("openings", []) if not o.get("_used")]
    if unused:
        print("  aviso: %d vano(s) sin muro asociado" % len(unused))
        for o in unused[:8]:
            print("    ", o["level"], o["rect"], o["kind"])
    return m


# ----------------------------------------------------------------- exportar
MATS = {
    "muro":       ((0.945, 0.937, 0.918), 1.0),
    "muro_int":   ((0.898, 0.886, 0.867), 1.0),
    "cubierta":   ((0.267, 0.286, 0.306), 1.0),
    "losa":       ((0.855, 0.843, 0.812), 1.0),
    "vidrio":     ((0.596, 0.749, 0.878), 0.40),
    "pavimento":  ((0.906, 0.886, 0.827), 1.0),
    "terreno":    ((0.588, 0.647, 0.451), 1.0),
    "madera":     ((0.780, 0.663, 0.514), 1.0),
    "mueble":     ((0.741, 0.749, 0.757), 1.0),
}


def export_obj(mesh, path):
    base = os.path.basename(path)
    with open(path + ".mtl", "w") as f:
        for name, (c, a) in MATS.items():
            f.write("newmtl %s\nKd %.3f %.3f %.3f\nKa 0.1 0.1 0.1\n"
                    "Ks 0.05 0.05 0.05\nd %.2f\nillum 2\n\n" % (name, c[0], c[1], c[2], a))
    with open(path + ".obj", "w") as f:
        f.write("# generado por build3d.py\nmtllib %s.mtl\n" % base)
        idx = 1
        for mat, arr in mesh.groups.items():
            f.write("\ng %s\nusemtl %s\n" % (mat, mat))
            n = len(arr) // 9
            for i in range(n * 3):
                f.write("v %.4f %.4f %.4f\n" % (arr[i * 3], arr[i * 3 + 1], arr[i * 3 + 2]))
            for i in range(n):
                f.write("f %d %d %d\n" % (idx, idx + 1, idx + 2))
                idx += 3
    return path + ".obj"


def export_html(mesh, spec, path, template):
    data = {"groups": {k: [round(v, 4) for v in a] for k, a in mesh.groups.items()},
            "mats": {k: {"c": "#%02x%02x%02x" % tuple(int(x * 255) for x in v[0]),
                         "o": v[1]} for k, v in MATS.items()},
            "meta": spec.get("meta", {}),
            "bbox": spec.get("bbox", [0, 0, 14, 14])}
    html = template.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    spec_path = sys.argv[1]
    out = "modelo"
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    spec = json.load(open(spec_path, encoding="utf-8"))
    mesh = build(spec)
    tris = sum(len(a) for a in mesh.groups.values()) // 9
    print("  %d triángulos en %d materiales" % (tris, len(mesh.groups)))
    export_obj(mesh, out)
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "viewer_template.html"), encoding="utf-8").read()
    export_html(mesh, spec, out + ".html", tpl)
    print("  ->", out + ".obj", "/", out + ".html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
