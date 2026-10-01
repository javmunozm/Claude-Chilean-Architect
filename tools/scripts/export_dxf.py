"""Export a FreeCAD document to DXF.

Paths come from the environment, not argv - freecadcmd imports bare arguments
as model files. See docs/system.md, Known issues.

    MODEL=<in.FCStd> OUT=<out.dxf> "E:/FreeCAD/bin/freecadcmd.exe" \
        tools/scripts/export_dxf.py
"""
import os
import sys


def main():
    model = os.environ.get("MODEL")
    out = os.environ.get("OUT")
    if not model or not out:
        print("usage: MODEL=<in.FCStd> OUT=<out.dxf> freecadcmd "
              "tools/scripts/export_dxf.py", file=sys.stderr)
        return 2

    import FreeCAD
    import importDXF

    doc = FreeCAD.openDocument(model)
    doc.recompute()

    objs = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape
            and not o.Shape.isNull()]
    if not objs:
        print("error: no shaped objects to export", file=sys.stderr)
        return 1

    importDXF.export(objs, out)
    size = os.path.getsize(out) if os.path.exists(out) else 0
    print("exported %s (%d objects, %d bytes)" % (out, len(objs), size))
    return 0


# freecadcmd imports rather than executes: accept the module name too.
if __name__ in ("__main__", "export_dxf"):
    _rc = main()
    if _rc:
        sys.exit(_rc)
