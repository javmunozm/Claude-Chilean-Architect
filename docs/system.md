# Toolchain

Versions here were **measured on this machine on 2026-09-18**, not assumed. If a
command below fails, re-probe before trusting the rest of this file.

## Installed and verified

| Tool | Version | Location | Verified how |
|------|---------|----------|--------------|
| FreeCAD | 1.1.3 (Libs 1.1.3R20260725) | `E:/FreeCAD/` | `freecadcmd` + `FreeCAD.Version()` |
| — bundled Python | 3.11.14 | `E:/FreeCAD/bin/python.exe` | `sys.version` inside freecadcmd |
| — Arch / Draft | present | `E:/FreeCAD/Mod/` | `import Arch, Draft` succeeded |
| — TechDraw | present | `E:/FreeCAD/Mod/` | `import TechDraw` succeeded |
| — IfcOpenShell | 0.8.4 | bundled with FreeCAD | `ifcopenshell.version` |
| Blender | 5.2.0 LTS (build 2026-07-14) | `E:/Blender/` (on PATH) | `blender --version` |
| — bundled Python | — | `E:/Blender/5.2/python/bin` | directory present |
| System Python | 3.13.5 | `C:/Python313/` | `python --version` |
| — ezdxf | 1.4.4 | system site-packages | `pip list` |
| — shapely | 2.1.2 | system site-packages | `pip list` |
| — numpy | 2.3.2 | system site-packages | `pip list` |
| — matplotlib | 3.10.7 | system site-packages | `pip list` |
| git | 2.37.3.windows.1 | on PATH | `git --version` |

## Not installed

| Expected | Status | Consequence |
|----------|--------|-------------|
| `ifcopenshell` in **system** Python | **absent** | IFC work must run inside FreeCAD's interpreter, where 0.8.4 is bundled. `import ifcopenshell` under Python 3.13 raises ImportError. |
| LibreOffice | **not verified** | `docs/commands.md` assumes budgets are opened manually. Probe before scripting Calc. |
| FreeCAD / Blender on PATH as `freecad` | absent | Call binaries by absolute path, as every command in this repo does. |

## Three interpreters, not one

This is the single most common source of confusion here:

| Interpreter | Version | Has | Use for |
|-------------|---------|-----|---------|
| System `python` | 3.13.5 | ezdxf, shapely, numpy | `norm_check.py`, `render_check.py` |
| `freecadcmd.exe` | 3.11.14 | FreeCAD, Arch, ifcopenshell | `area_calc.py`, any Arch geometry |
| Blender's Python | bundled | bpy | Blender scripts via `--python` |

Packages installed into one are **not** visible to the others. `pip install` under
the system Python does nothing for FreeCAD scripts.

## Known issues

### 1. `freecadcmd` imports your script instead of running it

**Measured on FreeCAD 1.1.3.** A script run as `freecadcmd script.py` is loaded
with `__name__` set to the module name (`"script"`), not `"__main__"`.

Consequence: the standard guard never fires, so the script loads, defines its
functions, does nothing, and **exits 0**. It looks like success and produces no
output. This cost real debugging time during this repo's setup.

```python
# WRONG under freecadcmd — silently does nothing
if __name__ == "__main__":
    main()

# CORRECT — accept both entry points
if __name__ in ("__main__", "area_calc"):
    main()
```

### 2. `freecadcmd` treats bare arguments as files to import

Anything on the command line after the script is interpreted as a **model file to
open**. Passing an output path positionally makes FreeCAD try to import it:

```
<class 'FileNotFoundError'>: [Errno 2] No such file or directory: 'extract.json'
Exception while processing file: extract.json
```

This is why `tools/area_calc.py` takes `AREA_CALC_MODEL` and `AREA_CALC_OUT` from
the **environment**. Environment variables do propagate into `freecadcmd`
correctly — that part was tested and works.

### 3. `freecadcmd` resets the shell working directory

Every invocation prints `Shell cwd was reset to ...` on exit. Use absolute paths
in scripts that run after it in the same shell session.

### 4. Progress output floods stderr with carriage returns

FreeCAD emits `Recompute...(33 %)` progress on a single line using `\r`. To read
real output, filter it:

```bash
freecadcmd script.py 2>&1 | tr '\r' '\n' | grep -v '([0-9]* %)'
```

### 5. Bounding-box widths overstate non-rectangular rooms

`area_calc.py` derives `min_width` from the shape's bounding box. For an L-shaped
room this is wider than the true clear width. The extract flags this via
`rectangularity` (< 0.95) and a `_warning` field. Accessibility and circulation
verdicts on such a room need form-auditor to measure it properly.

### 6. Door clear width is deliberately not computed

`area_calc.py` records a door's nominal leaf `width` but never a `clear_width`.
Clear passage depends on frame, stop and opening angle, none of which are in the
Arch object. The norm rule therefore reports SKIP rather than a false PASS — this
is intentional, not a gap to be patched by estimating.

### 7. A print with "ñ" can stop a script silently

In a console whose encoding is not UTF-8, printing a Spanish label ("Baño") raises
`UnicodeEncodeError`. `freecadcmd` swallows it and the script ends before its
self-checks. Measured 2026-10-02 under the C locale, see [lessons.md](lessons.md).
Scripts that print labels add, after `import FreeCAD`:

```python
try:
    sys.stdout.reconfigure(errors="replace")    # "Baño" prints as "Ba?o" instead of aborting
except Exception:
    pass
```

or run with `PYTHONIOENCODING=utf-8`.
