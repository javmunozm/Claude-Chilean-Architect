#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Renderiza un DXF a PNG para poder MIRAR el plano.

El repositorio exige abrir y mirar el plano tras cada cambio de geometria; esto
lo hace posible sin abrir un CAD. No sustituye la revision en CAD: es una vista
de control.

    python tools/scripts/dxf_preview.py <archivo.dxf> -o <salida.png>
"""
from __future__ import annotations

import argparse
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
except ImportError:
    print("error: falta ezdxf", file=sys.stderr)
    raise SystemExit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dxf")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args(argv)

    doc = ezdxf.readfile(args.dxf)
    msp = doc.modelspace()

    fig = plt.figure(figsize=(20, 15))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()

    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)

    fig.savefig(args.out, dpi=args.dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print("vista: %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
