# ArquiCL — Chilean Architecture Project System

AI-managed architectural design and integration platform. Each subfolder under
`projects/` is one building or intervention. Plans are authored in FreeCAD; 3D
visualization and rendering in Blender.

**This file is the constitution. It is loaded automatically; everything else is
read on demand.** If a rule here conflicts with any other document in this repo,
this file wins.

## CORE DIRECTIVE

1. **Do what you are told.** Execute the task as given. Do not re-scope it, do not
   substitute a different task, do not refuse it because you predict it will find
   nothing. If it finds nothing, run it and report nothing.
2. **No changes without permission.** Propose first; edit only after the user
   approves. This covers production files, docs, and memory.
3. **No claims without testing.** Do not assert a result, a mechanism, or a null
   from reasoning alone. Measure it, or say you have not measured it.
4. **Do not fabricate tests to support a claim.** No test built to reach a
   conclusion already chosen, and no reporting of a test that was not actually run.
5. **Chilean norms are law, not suggestions.** Every dimensional, structural, and
   programmatic decision must cite the specific norm article it satisfies. An
   uncited decision is an unverified one.

Methodology on this project is the user's call. Report what a run produced; do not
gate the user's decisions behind conditions of your own.

## What this means in practice here

**A remembered number is not a citation.** This is directive 3 and 5 together, and
it is the rule this repo most often tempts you to break. `tools/norms/rules.json`
currently marks every threshold `UNVERIFIED`; `tools/norm_check.py` will not return
PASS for any of them. When it reports INCONCLUSIVE, report INCONCLUSIVE — do not
substitute a value you recall to produce a cleaner answer.

**A render is not a measurement.** A picture can hide a missing wall behind a
camera angle or flatter a 2.10 m ceiling. Ask `form-auditor` for a number before
believing an image, and `norm-checker` before signing off on compliance.

**A plan that opens without error can still be physically wrong.** After any
geometry change: export, gate it, then **open the export and look at it**. The gate
proves a current non-trivial file exists. It cannot see a wall in the wrong place.

**INCONCLUSIVE is a real answer.** It is correct when a threshold is untranscribed,
when a verdict needs a structural calculation this repo cannot run, or when the
model lacks the geometry to measure. Converting an unmeasured question into a
confident PASS is a worse outcome than an honest gap.

## Two rules that cost this repo the most

- **A version is never a sibling folder.** Nest it as `projects/<Project>/v2/`.
  Never delete an old version — v2 may import from `v0/plans/`.
  See [docs/versioning.md](docs/versioning.md).
- **Never delete an attempt on your own judgment.** Only an explicit rejection from
  the user triggers cleanup, and the lesson gets recorded in the project README
  before the folder goes. "Clean this up" is not a rejection of any specific
  attempt — ask which. See [docs/attempts.md](docs/attempts.md).

## Toolchain — the three-interpreter trap

Versions measured on this machine 2026-09-18. **Neither FreeCAD nor Blender is on
PATH as `freecad`** — call binaries by absolute path.

| Interpreter | Version | Has | Use for |
|-------------|---------|-----|---------|
| System `python` | 3.13.5 | ezdxf 1.4.4, shapely, numpy | `norm_check.py`, `render_check.py` |
| `E:/FreeCAD/bin/freecadcmd.exe` | 3.11.14 | FreeCAD 1.1.3, Arch, ifcopenshell 0.8.4 | `area_calc.py`, all Arch geometry |
| Blender's bundled Python | — | bpy (Blender 5.2.0 LTS, on PATH) | Blender scripts via `--python` |

Packages installed into one are **not** visible to the others. `pip install` under
system Python does nothing for FreeCAD scripts. `import ifcopenshell` fails under
Python 3.13 — IFC work runs inside FreeCAD.

### Two freecadcmd quirks that will waste your afternoon

Both measured, both in [docs/system.md](docs/system.md):

1. **It imports your script instead of running it.** `__name__` is the module name,
   not `"__main__"`, so a standard guard never fires — the script loads, does
   nothing, and **exits 0 looking like success**. Write
   `if __name__ in ("__main__", "<module>"):`.
2. **Bare arguments are treated as files to import.** Passing an output path
   positionally makes FreeCAD try to open it as a mesh. Pass paths via
   **environment variables**.

## The verification sweep

Run after any geometry change:

```bash
# 1. measure the model (paths in the environment, not argv)
AREA_CALC_MODEL=projects/<Name>/plans/model.FCStd \
AREA_CALC_OUT=projects/<Name>/calcs/model_extract.json \
  "E:/FreeCAD/bin/freecadcmd.exe" tools/area_calc.py

# 2. check dimensional rules (exit 1 on FAIL *or* UNVERIFIED)
python tools/norm_check.py projects/<Name>/calcs/model_extract.json \
  --site projects/<Name>/site.json

# 3. confirm exports are current (MISSING / THIN / STALE)
python tools/render_check.py projects/<Name>

# 4. open the export and look at it   <- not optional, not automatable
```

Step 4 catches what steps 1–3 structurally cannot.

## Conventions that are load-bearing

**Build with Arch objects** — Wall, Space, Window, Door, Slab, Structure. Not raw
Part solids: `area_calc.py` reads the Arch graph, and geometry invisible to it is
never checked by the norm checker.

**Label Spaces in Spanish, as an architect would** — `Dormitorio Principal`,
`Estar`, `Pasillo`, `Baño Accesible`. Labels select which norm rules apply, so a
space called `Room001` gets no tags and no checks. Table in
[docs/architecture.md](docs/architecture.md).

**Units:** metres for architecture, centimetres for details, millimetres for
joinery/steel. FreeCAD works internally in millimetres; the tools convert on the
way out. A 1000× slip is the most dangerous error here because the numbers stay
plausible in isolation.

**Coordinates:** origin at the **northwest corner of the site** at ground level,
**+X east**, **+Y south**, **+Z up**. Levels referenced to NPT and NCR per OGUC.

**`site.json` is machine-read**, not documentation. It carries the per-site limits
that cannot be national constants — PRC ceilings, NCh 1079 thermal zone, NCh 433
seismic zone and soil type. A null there makes dependent rules report SKIP or
UNVERIFIED, which is correct. A guessed value makes them report PASS, which is a
fabricated verdict. **Never copy `prc_limits` between projects** — they vary by
comuna and by zone within a comuna.

## Agents

Eleven norm-aware subagents in `.claude/agents/`, documented in
[docs/agents.md](docs/agents.md). Handoff order:

```
site-analyst → program-architect → plan-drafter → structural-reviewer →
thermal-reviewer → fire-safety-reviewer → accessibility-reviewer →
installations-reviewer → 3d-modeler → form-auditor → spec-writer
```

Each stage hands off explicitly rather than re-deriving the previous stage's
decisions. On questions of fact, `form-auditor` outranks renders and drawings, and
measured extracts outrank the stated program.

`structural-reviewer` reviews configuration only — this repo has **no solver**. A
verdict needing computed forces is INCONCLUSIVE with a handoff to a calculista.

## Documentation

| Doc | Covers |
|-----|--------|
| [docs/architecture.md](docs/architecture.md) | Repo structure, pipeline, naming and unit conventions |
| [docs/agents.md](docs/agents.md) | The subagents, handoff order, how to brief them |
| [docs/norms.md](docs/norms.md) | Norms index, per-agent map, how to transcribe a threshold |
| [docs/commands.md](docs/commands.md) | Standard commands: measure, check, export, render |
| [docs/system.md](docs/system.md) | Full toolchain with measured versions, known issues |
| [docs/versioning.md](docs/versioning.md) | Nesting a version, the move procedure |
| [docs/attempts.md](docs/attempts.md) | `attempts/`, the record-then-delete procedure |
| [docs/projects.md](docs/projects.md) | Index of all projects with description and status |
| [docs/lessons.md](docs/lessons.md) | Post-mortems — one entry per incident, measured causes |
| [docs/region_concepcion.md](docs/region_concepcion.md) | Gran Concepción: applicable instruments (DS 15 thermal, PPDA, NCh 433/DS 61, PRMC) and their verification status |

`sources/` and `tools/` stay at the repo root, shared across all projects — never
nested under `projects/`, because a tool copied into a project stops receiving fixes.
