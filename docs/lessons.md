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
