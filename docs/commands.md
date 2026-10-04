# Standard commands

All commands assume the repo root `D:/CAD/Claude-CAD-builds` as the working
directory. Binaries are called by absolute path because neither FreeCAD nor
Blender is on PATH under a predictable name (`blender` is, `freecad` is not).

## Measure a model

Extracts real geometry into the JSON that the norm checker consumes. Runs inside
FreeCAD's interpreter; paths go in the **environment**, never in argv (see
[system.md](system.md), Known issues #2).

```bash
AREA_CALC_MODEL=projects/<Name>/versions/<vN>/exports/model/<model>.FCStd \
AREA_CALC_OUT=projects/<Name>/versions/<vN>/calcs/model_extract.json \
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
python tools/norm_check.py projects/<Name>/versions/<vN>/calcs/model_extract.json \
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
python tools/render_check.py projects/<Name>/versions/<vN>
python tools/render_check.py projects/<Name>/versions/<vN> --require dxf,pdf,png
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
MODEL=projects/<Name>/versions/<vN>/exports/model/<model>.FCStd \
OUT=projects/<Name>/versions/<vN>/exports/drawings/plan.dxf \
  "E:/FreeCAD/bin/freecadcmd.exe" tools/scripts/export_dxf.py
```

## Render in Blender

```bash
blender --background projects/<Name>/versions/<vN>/exports/model/<file>.blend \
        --python tools/scripts/render.py
```

Blender 5.2.0 LTS is on PATH. Its bundled Python is separate from the system
Python — packages do not cross over.

Then gate the result:

```bash
python tools/render_check.py projects/<Name>/versions/<vN> --require png
```

## Verify a 3D model: roofs, slits, coincident faces

```bash
python tools/scripts/verificar_modelo3d.py projects/<Name>/versions/<vN>/exports/model/<model>.obj \
  --spec <plan>.json [--recintos <rooms>.json] \
  [--desfase-y 14 | --y-directo] [--json]
```

Measures the OBJ, whatever produced it:
- **uncovered area** per room, from vertical rays;
- **rays that escape** horizontally between the highest door head and the ceiling,
  meaning a slit between wall and roof;
- **coincident faces**: coplanar overlapping faces with the same orientation
  (z-fighting);
- **unpaired roof edges**.

**Exit:** `1` on any uncovered area or escaping ray.

- **Frame flag**, set by the exporter:

  | Exporter | Flag |
  |----------|------|
  | FreeCAD v2 `export_obj.py` | `--desfase-y 14` |
  | Blender `wm.obj_export` | `--desfase-y 0` |
  | `build3d.py` | `--y-directo` |

- **Triangulated OBJ only.** From Blender, export with
  `export_triangulated_mesh=True`. A concave n-gon fanned by the reader overlaps
  itself and is counted as coincident faces.
- **Without `--recintos`** the interior is the union of the slabs. A covered porch
  then counts as interior, and its rays "escape" through the open front: 60 false
  escapes on CasaPatioInterior v0.
- **Rays are 0.25 m apart**, so a narrower slit can pass between them. A residual
  coincident area is a defect until located. Look at the views too.

## Control views of an OBJ

```bash
VISTAS_OBJ=<model.obj> VISTAS_OUT=<folder> \
  blender --background --python tools/scripts/vistas_obj.py
```

Writes `3d_noreste.png` and `3d_suroeste.png`: orthographic, Cycles on CPU by default
(`VISTAS_MOTOR=BLENDER_WORKBENCH` is faster with a GPU). The script assumes the v2
frame, with north toward −Z of the OBJ. An OBJ from `build3d.py` comes out mirrored,
which is fine for checking surfaces but not for orientation.

## 3D builders share one roof module

| Builder | Output | Command |
|---------|--------|---------|
| `tools/scripts/blender_build.py` | `.blend` | `BUILD_SPEC=<plan.json> BUILD_OUT=<file.blend> blender --background --python tools/scripts/blender_build.py` |
| `tools/scripts/build3d.py` | `.obj/.mtl` (+ `.html` viewer) | `python tools/scripts/build3d.py <plan.json> --out <path/name>` |
| `projects/<Name>/versions/<vN>/scripts/build_model.py` | `.FCStd` (Arch) | see that version's README |

All three take roofs, gables, closures under roof edges and wall junctions from
`tools/cubierta.py`. A change to roof or junction logic goes there, and is then
re-measured on every output with `verificar_modelo3d.py`.

## The drawing set: plans, roof plan, elevations, sections

From `projects/CasaPatioInterior/versions/v4/` on, a version's `scripts/` produce a
set of A2 sheets at true scale:
- `lamina.py`: frame, title block (from `source/proyecto.json` and `site.json`),
  sheet number, date, PDF at paper size, DXF paper-space layout;
- `export_views.py` (FreeCAD): roof plan, 4 elevations and 2 sections, with hidden
  lines removed;
- `make_dxf.py`: the floor plans;
- `make_views.py`: the remaining sheets, then the PDF of the whole set.

```bash
V2_DIR=$PWD/$P VIEWS_MODEL=$M VIEWS_OUT=$PWD/$P/calcs/views_data.json "$F" $P/scripts/export_views.py
python $P/scripts/make_dxf.py && python $P/scripts/make_views.py
```

Check the PDF page size after any change to the sheet code. ezdxf's `finalize()`
shrinks the figure, which is how v2/v3 shipped "1:50" sheets at ~1:172
(docs/lessons.md).

## Drainage, finishes, structure, details and EETT (v5 on)

`projects/CasaPatioInterior/versions/v5/` adds these to the drawing set. Order matters:
each step reads the previous one's output.

```bash
# gutters and downpipes (system Python; build_model.py reads the JSON into the model)
python tools/aguas_lluvias.py <plan.json> --site projects/<Name>/site.json -o $P/calcs/aguas_lluvias.json

# structural predimensioning + report (after measuring the model)
python tools/estructura.py <plan.json> --extract $P/calcs/model_extract.json \
  --site projects/<Name>/site.json --propuesta $P/source/estructura.json \
  --recintos $P/calcs/recintos_vN.json -o $P/calcs/estructura_calc.json \
  --memoria $P/exports/memoria_calculo_vN.md
python tools/md_pdf.py $P/exports/memoria_calculo_vN.md

# sheets: plans, details (sheet 6), then the other views and the PDF of the set
python $P/scripts/make_dxf.py && python $P/scripts/make_details.py && python $P/scripts/make_views.py

# EETT + quantity take-off (CSV with empty price columns)
python $P/scripts/make_eett.py
```

`tools/md_pdf.py` prints through headless Chrome, Edge or Chromium. A LibreOffice
install with only `libreoffice-core` has no Writer and cannot convert HTML (measured).

## Doors: hinge, swing and missing doors

```bash
python tools/puertas.py projects/<Name>/versions/<vN>/calcs/plan_data.json -o <puertas.json> \
  [--recintos <recintos.json>]
```

`tools/scripts/json_to_dxf.py` and v2's `derive_puertas.py` call the same module
and take the same two options.
- **The user indicates doors first.** An opening that carries `operation`,
  `hinge` or `swing` is honoured, and so is an indicated opening without a leaf
  (`open`). The rest follow rules R1–R9, which are a design convention, not a norm
  (see `projects/CasaPatioInterior/versions/v2/README.md`).
- **Generated when not indicated**, marked `*`:
  - every bedroom-type room ("dormitorio", "pieza", "habitación") gets a door of
    its own;
  - every other room that cannot be reached gets one.
- **Stairs and corridors never get a generated door.** An unreachable one is only
  reported. Add `--puertas-circulacion` to generate them, and
  `--con-puerta <word>` to make more rooms require a door.
- Unlabeled regions are reported, never given a door.

**Exit:** `1` if a room cannot be reached.

## Full verification sweep

The sequence to run after any geometry change:

```bash
# 1. measure the model
AREA_CALC_MODEL=projects/<Name>/versions/<vN>/exports/model/<model>.FCStd \
AREA_CALC_OUT=projects/<Name>/versions/<vN>/calcs/model_extract.json \
  "E:/FreeCAD/bin/freecadcmd.exe" tools/area_calc.py

# 2. check the dimensional rules
python tools/norm_check.py projects/<Name>/versions/<vN>/calcs/model_extract.json \
  --site projects/<Name>/site.json

# 3. confirm exports are current
python tools/render_check.py projects/<Name>/versions/<vN>

# 3b. 3D model: no uncovered sector, no slit, no coincident faces, closed roof
python tools/scripts/verificar_modelo3d.py projects/<Name>/versions/<vN>/exports/model/<model>.obj \
  --spec <plan>.json --recintos <rooms>.json   # frame flag: see above

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
