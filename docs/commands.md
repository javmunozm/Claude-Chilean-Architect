# Standard commands

All commands assume the repo root `D:/CAD/Claude-CAD-builds` as the working
directory. Binaries are called by absolute path because neither FreeCAD nor
Blender is on PATH under a predictable name (`blender` is, `freecad` is not).

## Measure a model

Extracts real geometry into the JSON that the norm checker consumes. Runs inside
FreeCAD's interpreter; paths go in the **environment**, never in argv (see
[system.md](system.md), Known issues #2).

```bash
AREA_CALC_MODEL=projects/<Name>/plans/<model>.FCStd \
AREA_CALC_OUT=projects/<Name>/calcs/model_extract.json \
  "E:/FreeCAD/bin/freecadcmd.exe" tools/area_calc.py
```

Omit `AREA_CALC_OUT` to print to stdout. To read the output past FreeCAD's
progress spam:

```bash
... 2>&1 | tr '\r' '\n' | grep -v '([0-9]* %)'
```

**Expected output:** `wrote <path>  (N entities, X.XX m2 of space)`.
If it reports 0 entities, the model has no Arch objects — raw Part solids are
invisible to the extractor, and an invisible room is an unchecked room.

## Check compliance

```bash
python tools/norm_check.py projects/<Name>/calcs/model_extract.json \
  --site projects/<Name>/site.json
```

Add `--json` for machine-readable output.

**Exit codes:** `0` only when every evaluated rule passed. `1` when anything
failed **or** was UNVERIFIED. `2` on a missing file.

Note the deliberate design: UNVERIFIED is non-zero. A threshold that was never
transcribed from the official text yields no verdict, so an unverified run is a
blocked run, not a quiet pass. See [norms.md](norms.md).

## Verify exports exist and are current

```bash
python tools/render_check.py projects/<Name>
python tools/render_check.py projects/<Name> --require dxf,pdf,png
```

Catches three failure modes mechanically: **MISSING** (no such export), **THIN**
(below the byte floor — almost certainly a blank sheet), **STALE** (older than the
model that should have produced it).

A green gate means a current, non-trivial file exists. It does not mean the plan
is right. **Open the export and look at it.**

## Export from FreeCAD

Write a small script and run it headless, remembering both freecadcmd quirks —
module-name entry point, and no bare path arguments:

```python
# tools/scripts/export_dxf.py
import os, FreeCAD, importDXF

doc = FreeCAD.openDocument(os.environ["MODEL"])
doc.recompute()
objs = [o for o in doc.Objects if o.ViewObject is None or True]
importDXF.export(objs, os.environ["OUT"])
print("exported", os.environ["OUT"])

if __name__ in ("__main__", "export_dxf"):
    pass
```

```bash
MODEL=projects/<Name>/plans/model.FCStd \
OUT=projects/<Name>/exports/plan.dxf \
  "E:/FreeCAD/bin/freecadcmd.exe" tools/scripts/export_dxf.py
```

## Render in Blender

```bash
blender --background projects/<Name>/model/<file>.blend \
        --python tools/scripts/render.py
```

Blender 5.2.0 LTS is on PATH. Its bundled Python is separate from the system
Python — packages do not cross over.

Then gate the result:

```bash
python tools/render_check.py projects/<Name> --require png
```

## Full verification sweep

The sequence to run after any geometry change:

```bash
# 1. measure the model
AREA_CALC_MODEL=projects/<Name>/plans/model.FCStd \
AREA_CALC_OUT=projects/<Name>/calcs/model_extract.json \
  "E:/FreeCAD/bin/freecadcmd.exe" tools/area_calc.py

# 2. check the dimensional rules
python tools/norm_check.py projects/<Name>/calcs/model_extract.json \
  --site projects/<Name>/site.json

# 3. confirm exports are current
python tools/render_check.py projects/<Name>

# 4. open the export and look at it   <- not optional, not automatable
```

Step 4 is the one that catches walls in the wrong place. Steps 1–3 cannot.

## Start a new project

```bash
mkdir -p projects/<Name>/{plans,model,exports,specs,calcs,attempts}
cp templates/README.template.md projects/<Name>/README.md
cp templates/site.template.json projects/<Name>/site.json
```

Then brief `site-analyst` to fill `site.json` from the site's certificate. Until
it holds real PRC limits and a thermal zone, several rules cannot be evaluated.
