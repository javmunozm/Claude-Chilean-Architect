# Lessons

Post-mortems. One entry per incident, read by the agents each concerns.

Every entry carries a **measured** cause, not a guess. An entry that says "seemed
to be a caching issue" teaches nothing and will be re-debugged by the next person.

## Format

```markdown
### YYYY-MM-DD — Short title
**Concerns:** agent(s) or tool(s)
**Symptom:** what was observed
**Cause:** what was actually happening, measured
**Fix:** what changed
**Carry forward:** the generalisable lesson
```

---

### 2026-09-18 — freecadcmd imports scripts instead of running them

**Concerns:** `plan-drafter`, `form-auditor`, anything scripting FreeCAD

**Symptom:** `tools/area_calc.py` produced no output and wrote no file when run
under `freecadcmd`. Exit code 0. No error, no traceback — it simply did nothing,
which read as success.

**Cause:** measured, not assumed. A probe script printing `__name__` under
`freecadcmd` returned the **module name** (`nameprobe`), not `__main__`. FreeCAD
1.1.3 imports the script rather than executing it as a main module, so the
standard `if __name__ == "__main__":` guard never fired.

An earlier hypothesis — that environment variables were not propagating into the
Windows binary — was tested directly and **disproved**: `AREA_CALC_MODEL=hello
freecadcmd envprobe.py` printed `MODEL= 'hello'` correctly. Testing the guess
rather than acting on it is what found the real cause.

**Fix:** accept both entry points:
```python
if __name__ in ("__main__", "area_calc"):
```

**Carry forward:** a silent exit-0 from `freecadcmd` usually means the script
loaded and no entry point fired. Check `__name__` before suspecting anything else.
A plausible hypothesis that goes untested costs more than the test would have.

---

### 2026-09-18 — freecadcmd treats bare arguments as files to import

**Concerns:** `plan-drafter`, `form-auditor`, `docs/commands.md`

**Symptom:** running `freecadcmd tools/area_calc.py -- fixture.FCStd -o extract.json`
aborted with:
```
<class 'FileNotFoundError'>: [Errno 2] No such file or directory: 'extract.json'
Exception while processing file: extract.json
```
The traceback came from FreeCAD's **FEM mesh importer** — nothing to do with the
script.

**Cause:** `freecadcmd` interprets every bare argv entry after the script as a
model file to open, and tried to import the not-yet-written output path as a mesh.

**Fix:** `area_calc.py` takes `AREA_CALC_MODEL` and `AREA_CALC_OUT` from the
environment. Every documented command in this repo follows that pattern.

**Carry forward:** never pass paths positionally to `freecadcmd`. A traceback
pointing into a FreeCAD importer for a file you meant as an argument is this bug.

---

### 2026-09-18 — A threshold that exists is not a threshold that is verified

**Concerns:** `norm-checker` and every reviewer agent, `tools/norm_check.py`

**Symptom:** the first build of `norm_check.py` printed confident PASS and FAIL
verdicts against thresholds whose `source` field read `"UNVERIFIED"`. The run
looked authoritative: real measured geometry, real article citations, a clean
`VERDICT: NON-COMPLIANT`. It was tested on a fixture with a 2.10 m room and
correctly flagged it.

**Cause:** the code gated only on whether a threshold value was `None`, never on
where the value came from. Numbers written from recollection during the initial
build passed that check and produced verdicts indistinguishable from verified ones.

**Fix:** added `unverified_reason()`, which gates on `source` as well as presence.
A rule marked `UNVERIFIED` now returns INCONCLUSIVE and still reports the measured
value, so the geometry work is not wasted. A threshold supplied from a project's
`site.json` counts as sourced, because the PRC certificate is the citation.

**Carry forward:** the dangerous failure is not a missing number — it is a present
number with no provenance, because it looks exactly like a verified one in the
output. Check where a value came from, not just whether it is there. This is
CORE DIRECTIVE 3 as executable code rather than as a good intention.

---

### 2026-10-01 — Plan DXFs unreadable: SHX font, 1.4 mm text, doors as rectangles

**Concerns:** `plan-drafter`, `tools/scripts/json_to_dxf.py`, `tools/scripts/dxf_preview.py`

**Symptom:** the plans in `projects/CasaPatioInterior/planos/` were hard to read.
Text was almost illegible, doors were indistinguishable from windows, and in the
PNG preview most of the walls were missing.

**Cause:** measured by inspecting the DXFs with ezdxf 1.4.4:
- All 238 TEXT entities in `planta_p1.dxf` used style `Standard`, whose font is `txt` (an AutoCAD
  SHX font). Viewers without that font substitute it.
- Text heights were 0.14–0.20 m in a drawing meant for 1:100. That is 1.4–2.0 mm
  on paper. The sheet also said "Escala 1:50 / 1:100", so no single scale was
  intended.
- Doors and windows were both plain rectangles on layer A-VANO: no leaf, no
  swing arc, no glazing line. Walls were not cut at the openings.
- Schedule and title block were on color 2 (yellow), and the openings on color 4
  (cyan). Both are near-invisible on white.
- The preview drew the walls (color 7) white on a white figure, because the
  renderer's default background policy was not set.

**Fix:** `json_to_dxf.py` now does the following:
- Sizes text in paper millimetres for `--escala` (default 1:100).
- Uses a TrueType style `ARQ` and its own dimension style (decimal comma).
- Unions and cuts walls with shapely and fills them (poché).
- Draws doors with leaf and arc, sliding doors with two leaves, and windows
  with sill and glass lines.
- Puts opening codes outside the wall, and draws the stair above the cut plane
  dashed.
- Adds an A3 paperspace sheet at scale.

`dxf_preview.py` forces a white background. Where a door's operation is not in
the JSON, the default used is stated in a note on the sheet.

**Carry forward:** text height is a paper quantity. Derive it from the plot scale,
never write it as a model length. And a preview that hides a whole layer is worse
than no preview, because it looks like a measurement of absence.

---

### 2026-10-01 — Roof built off its own plane: wedge faldones, ridge 0.22 m high, open attic

**Concerns:** `3d-modeler`, `form-auditor`, `tools/scripts/blender_build.py`

**Symptom:** in the renders of CasaPatioInterior the roof around the interior patio
showed steep wedges and dark open gaps.

**Cause:** measured on the built `.blend` (vertex z against the roof plane, plus
horizontal ray casts through the façade walls):
1. `construir_cubierta` ignored `x_ref` and treated every band edge as an eave.
   The two faldones cut back around the patio came out at **152.2 %** and
   **55.6 %** slope, against 35.7 % for the rest, deviating up to 1.34 m from the
   roof plane.
2. It took `eave_z`/`ridge_z` as the *underside* and extruded the thickness
   upward. The JSON, `build3d.py` and the gable profiles all treat them as the
   *top* face. Result: the ridge was at **+7.320** instead of the documented +7.10.
3. No wall closed the attic above the patio-facing walls of the 2nd floor:
   **39** test rays passed through between wall top and roof.
4. Data: in `casa_rev_h.json` (inherited from rev G), bands 2 and 3 started
   0.25 m *behind* the walls at y = 9.0 and 10.2 (9.25 and 10.45), instead of
   overhanging them (8.75 and 9.95) like bands 0 and 1.

**Fix:** roof plane from `x_ref`, with the thickness hung below the top face. New
`cerrar_bajo_cubierta` raises façade walls that sit under a roof edge with open
sky beside them, up to the roof (5 walls here). Band edges corrected in the
JSON. Re-measured: all gable faldones 35.7 %, shed 19.0 % (the source elevation
says 19 %), ridge **7.100 m**, **0** rays through.

**Carry forward:** a roof is one plane per slope. Any piece built from its own
local edges instead of the shared reference will drift as soon as a band is cut
back. When a port of a builder changes a convention (top versus underside),
re-measure a dimension the document states (here the ridge), not just the look.
