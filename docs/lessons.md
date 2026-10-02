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

---

### 2026-10-02 — The roof fix reached one of three builders

**Concerns:** `3d-modeler`, `form-auditor`, `tools/scripts/blender_build.py`,
`tools/scripts/build3d.py`, `projects/CasaPatioInterior/v2/plans/build_model.py`

**Symptom:** after the 2026-10-01 fix, the user still saw roofs that did not cover
whole sectors.

**Cause:** three generators each carried their own roof code, and the fix had gone
into one of them. Measured with `tools/scripts/verificar_modelo3d.py`, which casts
vertical and horizontal rays and pairs the roof edges on the OBJ:
- **v2 FreeCAD model** (`build_model.py`): **928** rays escaped from the 2nd floor
  between wall and roof over the patio. **25** roof edges were unpaired, so the roof
  was not a closed solid.
- **v0 interchange OBJ** (`build3d.py`, still on the original roof logic): **857**
  rays escaped and **29** roof edges were unpaired.
- **v0 `.blend`** (the builder that had been fixed): **25** roof edges unpaired. The
  terrain box was also 0.25 m above the floor (top at +0.25 instead of −0.15), so
  every upward probe on the ground floor hit it and no horizontal ray was cast there.

**Fix:** one shared module, `tools/cubierta.py`, used by all three builders. It
builds each roof as one closed solid on the plane given by `x_ref`. Gables are
clipped below the roof underside, and closures fill the space under roof edges. The
shed roof is cut where walls pass through it, and data gaps are reported
(`diagnostico`). Re-measured on all three outputs: **0** rays escape, **0** m²
uncovered, **0** unpaired roof edges.

**Carry forward:** when the same geometry is generated in more than one place, a fix
is not done until every output is re-measured, and the copies should become one
module. Measure the file the user opens, not the builder you edited.

---

### 2026-10-02 — Coincident faces: black stripes from overlapping solids

**Concerns:** `3d-modeler`, `form-auditor`, `tools/cubierta.py`, `tools/scripts/build3d.py`,
`tools/scripts/verificar_modelo3d.py`

**Symptom:** dark stripes and flicker on walls and roof edges in renders. After the
first round of fixes, one thin black vertical line remained in a patio corner.

**Cause:** coplanar triangles that overlap with the same orientation (z-fighting).
Measured:
- **53.14 m²** in v2:
  - wall/wall 25.8: walls drawn over their full axis length overlap at every corner;
  - slab/wall 20.1: wall tops ran through the slab;
  - roof/wall 7.1: gable tops coplanar with the roof top, and the shed's end face on
    the 2nd-floor wall.
- **88.0 m²** in the v0 OBJ. Of that, 48.8 m² was contact between solids that only
  *counted* as visible. Every box in `build3d.py` (slabs, stair, terrain, furniture,
  paving) had inward normals; signed volume per material was negative (slab
  −80.886 m³). `build3d.py` also inset the glass 2 cm from the jambs, which left a
  slit through the wall beside every opening. 7 rays escaped through one of them.
- **The last line.** In an L-corner, the trimming rule shortened only the
  higher-index wall. Interior wall 43 (0.12 m thick) overlapped the end of wall 22
  (0.20 m) by half its own thickness, so it could not be shortened, and neither wall
  was. That left a 6 cm × 2.5 m strip of coincident faces on the patio face. The
  verifier had been reporting it as **0.174 m²** of wall/wall. It showed up only in a
  view that faced that corner.

**Fix:**
- `cubierta.muros_ajustados` shortens a wall to the face of the wall it meets and
  stops walls under the slab above.
- In an L-corner it trims the other wall when the higher-index one cannot be
  trimmed.
- Under-roof closures are not shortened against a lower neighbour that has no
  closure of its own; otherwise the shortening would open a slit into the attic.
- In `build3d.py`, boxes are now wound outward and the glass reaches the jambs.

Measured on all three outputs:
- coincident area **0.144 m²**. That is the porch paving inside the ground slab, a
  quirk of the JSON, and the face is covered by the outer paving;
- plan overlap between walls: 0.6688 + 0.5104 m² → **0**;
- common volume among the 54 wall solids of v2: **0** m³. `wall_volume` went from
  81.872 to 77.114 m³ because corner overlaps are no longer counted twice.

**Carry forward:** a residual in a measurement is a defect until it is located: "0.174
m², small" was a visible black line. And a count of visible coincident faces trusts
the face orientation, so check signed volume before believing it.

---

### 2026-10-02 — freecadcmd swallowed a UnicodeEncodeError on "ñ"

**Concerns:** `plan-drafter`, every FreeCAD script that prints room names

**Symptom:** `build_model.py` finished without printing its self-check (`BUILD OK` or
the list of problems), with no traceback.

**Cause:** reproduced under the C locale. The first `print` of a label with "ñ"
("Baño 2") raised `UnicodeEncodeError` in the console encoding. `freecadcmd` swallows
exceptions from the scripts it imports, so the run ended silently before the checks.

**Fix:** the v2 FreeCAD scripts call `sys.stdout.reconfigure(errors="replace")` after
`import FreeCAD`. Under the C locale they now print "Ba?o 2" and reach `BUILD OK`.
Running with `PYTHONIOENCODING=utf-8` also works. See [system.md](system.md), Known
issue #7.

**Carry forward:** a `freecadcmd` run that stops before its last print hit an exception
you did not see. Spanish labels are data in this repo, so every script that prints
them must survive a console that is not UTF-8.

---

### 2026-10-02 — Generated doors in the wrong room: labels, not geometry

**Concerns:** `plan-drafter`, `tools/puertas.py`, `tools/scripts/json_to_dxf.py`

**Symptom:** while automatic door generation was being built, test runs did two wrong
things:
- they generated a door from the stair landing into Baño 3;
- they decided P06 of the 1st floor as if "Hall Escalera" were the stair.

**Cause:** measured on the room graph:
- the door came from an unlabeled 1.86 m² ledge of slab over the stair landing, which
  the tool treated as a room that needed access;
- the upper floor had no start point at the stair arrival;
- the stair test matched the substring "escalera", which also matches
  "Hall Escalera".

Separately, v0's approximate label points (finding 10 in its README) merge regions,
and the rules then choose wrong rooms. P01 "opens toward Cocina + Comedor + Galería
poniente" because the hall label lies in the porch.

**Fix:**
- Unlabeled regions are reported (`AVISO`, `residuales`) and never get a door.
- Upper floors start from the stair arrival.
- The stair test is `startswith("escalera")`.
- With v2's measured room polygons, `json_to_dxf.py` reproduces v2's 18 door
  decisions.

**Carry forward:** door rules are only as good as the room labels. A generator that
invents access for an unlabeled region is fabricating program; report the region
instead.
