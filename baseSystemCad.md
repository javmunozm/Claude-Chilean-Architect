# ArquiCL — Chilean Architecture Project System

AI-managed architectural design and integration platform. Each subfolder under
`projects/` is one building or intervention, with its own README. Plans are
authored in FreeCAD; 3D visualization and rendering in Blender.

## CORE DIRECTIVE

**The CORE DIRECTIVE lives in [CLAUDE.md](CLAUDE.md)**, which is loaded
automatically at the start of every session. It is reproduced there verbatim and
is authoritative.

It is not duplicated here on purpose: two copies of a rule set drift, and the copy
that drifts is always the one nobody loads. This file is the project index; the
constitution is `CLAUDE.md`.

In summary — do the task as given; propose before editing; no claim without a
measurement; never fabricate a test; every dimensional, structural or programmatic
decision cites its norm article.

## Verification

A plan that opens without error can still be physically wrong or normatively
non-compliant. After any geometry change **render a floor plan export** and
**look at it**; before trusting any structural verdict, check it against the
cited NCh article.

**A render is not a measurement.** Ask `form-auditor` for a number before
believing a picture, and `norm-checker` before signing off on compliance.

The mechanical half of this is the verification sweep in
[CLAUDE.md](CLAUDE.md#the-verification-sweep) and
[docs/commands.md](docs/commands.md).

## Documentation

| Doc | Covers |
|-----|--------|
| **[CLAUDE.md](CLAUDE.md)** | **The constitution — CORE DIRECTIVE, toolchain traps, verification sweep, load-bearing conventions. Auto-loaded every session.** |
| [docs/architecture.md](docs/architecture.md) | Repo structure, `sources/` vs `projects/`, FreeCAD plans → Blender 3D → exports → verification, project conventions |
| [docs/agents.md](docs/agents.md) | The subagents, their handoff order, and how to brief them |
| [docs/norms.md](docs/norms.md) | Chilean building norms index — NCh articles mapped to agent responsibilities |
| [docs/commands.md](docs/commands.md) | Standard commands: generate plans, export DXF/PDF, render 3D, verify compliance |
| [docs/system.md](docs/system.md) | Full toolchain — FreeCAD, Blender, packages with versions, known issues |
| [docs/versioning.md](docs/versioning.md) | Nesting a second version inside a project, the move procedure |
| [docs/attempts.md](docs/attempts.md) | `attempts/` folders, and the record-then-delete procedure when the user rejects work |
| [docs/projects.md](docs/projects.md) | Index of all projects with description and status |
| [docs/lessons.md](docs/lessons.md) | Post-mortems — one entry per incident, read by the agents each concerns |

## Agents

Norm-aware subagents, each responsible for a domain of Chilean building regulation
and design. Defined in `.claude/agents/`, documented fully in [docs/agents.md](docs/agents.md).

| Agent | Domain | Key norms |
|-------|--------|-----------|
| `site-analyst` | Terrain, orientation, site constraints, municipal plan compliance | OGUC Art. 2.1, PRC comunal |
| `program-architect` | Architectural programming — rooms, areas, circulation, zoning | OGUC Art. 4.1, NCh 1079 |
| `structural-reviewer` | Structural system review, seismic design verification | NCh 433, NCh 3171, NCh 2369 |
| `thermal-reviewer` | Thermal envelope, insulation, condensation risk | NCh 853, Art. 4.1.10 OGUC |
| `fire-safety-reviewer` | Fire resistance, egress, compartmentalization | OGUC Art. 4.3, NCh 935 |
| `accessibility-reviewer` | Universal accessibility compliance | OGUC Art. 4.1.7, Ley 20.422 |
| `installations-reviewer` | Electrical, plumbing, gas — layout and sizing | NCh Elec. 4/2003, NCh 2485 |
| `plan-drafter` | FreeCAD plan production — floor plans, sections, elevations, details | — |
| `3d-modeler` | Blender 3D modeling, visualization, and rendering | — |
| `form-auditor` | Auditing the real 3D form of a built model — cross-sections, volumes, built-vs-intended | — |
| `spec-writer` | Technical specifications (EETT), material schedules, itemized budgets | — |

## Handoff order

Typical flow for a new project:

```
site-analyst            (terrain, orientation, municipal constraints)
      ▼
program-architect       (program → zoning → area compliance)
      ▼
plan-drafter            (FreeCAD floor plans, sections, elevations)
      ▼
structural-reviewer     (structural system, seismic check)
      ▼
thermal-reviewer        (envelope, insulation, condensation)
      ▼
fire-safety-reviewer    (resistance, egress, compartments)
      ▼
accessibility-reviewer  (universal access compliance)
      ▼
installations-reviewer  (MEP layout and sizing)
      ▼
3d-modeler              (Blender 3D model and renders)
      ▼
form-auditor            (does the built form match intent?)
      ▼
spec-writer             (EETT, schedules, budget)
```

Each stage hands off explicitly rather than re-deriving the previous stage's
decisions.

## Toolchain summary

| Tool | Role |
|------|------|
| **FreeCAD** 1.1.3 (`E:/FreeCAD/`) | Plan authoring — floor plans, sections, elevations, details via Arch/BIM workbench |
| **Blender** 5.2.0 LTS (`E:/Blender/`, on PATH) | 3D modeling, visualization, and photorealistic rendering |
| **Python** 3.13.5 (system) | Scripting, automation, verification, norm-checking tools |
| **ezdxf** 1.4.4 | DXF read/write for plan interchange |
| **IFCOpenShell** 0.8.4 | IFC/BIM export — bundled inside FreeCAD, **not** in system Python |
| **LibreOffice Calc** | Itemized budgets and specification tables — presence not yet verified |

Versions above were measured on this machine, not assumed. Three separate Python
interpreters are in play (system, FreeCAD's 3.11, Blender's) and packages do not
cross between them. Full details and known issues in [docs/system.md](docs/system.md).

## Chilean norms — quick reference

The authoritative index is [docs/norms.md](docs/norms.md). Every agent reads its
own section before issuing a verdict.

> **Current state of the thresholds.** `tools/norms/rules.json` ships with every
> numeric limit marked `UNVERIFIED`, because a remembered value is not a citation
> (CORE DIRECTIVE 3 and 5). `tools/norm_check.py` refuses to return PASS for any
> rule in that state — it reports INCONCLUSIVE and still shows the measured value.
> The geometry pipeline is fully working; the limits to judge it against must be
> transcribed from the official texts first. See
> [docs/norms.md](docs/norms.md#transcribing-a-threshold).

| Norm | Scope |
|------|-------|
| **OGUC** (Ordenanza General de Urbanismo y Construcciones) | Master regulation — zoning, program, fire, accessibility, thermal |
| **NCh 433** | Seismic design of buildings |
| **NCh 3171** | Seismic design of non-structural components |
| **NCh 2369** | Seismic design of industrial structures |
| **NCh 1079** | Habitability — thermal zoning of Chile |
| **NCh 853** | Thermal conditioning — envelope requirements |
| **NCh 935** | Fire resistance classification |
| **NCh Elec. 4/2003** | Electrical installations |
| **NCh 2485** | Gas installations |
| **Ley 20.422** | Disability rights and universal accessibility |
| **PRC** (Plan Regulador Comunal) | Municipal zoning — project-specific, sourced per site |

## Repository structure

```
ArquiCL/
├── CLAUDE.md              ← the constitution: CORE DIRECTIVE, traps, conventions (auto-loaded)
├── baseSystemCad.md       ← this file: project index and doc pointers
├── docs/                  ← index-wide documentation (heavyweight .md files)
│   ├── architecture.md    ← repo structure, FreeCAD → Blender pipeline, conventions
│   ├── agents.md          ← subagents, handoff order, briefing protocol
│   ├── norms.md           ← Chilean norms index, per-agent responsibility map
│   ├── commands.md        ← standard commands: generate, export, render, verify
│   ├── system.md          ← full toolchain with versions, known issues
│   ├── versioning.md      ← nesting versions inside a project
│   ├── attempts.md        ← rejected work procedure
│   ├── projects.md        ← index of all projects
│   └── lessons.md         ← post-mortems with measured numbers
├── tools/                 ← shared tooling (norm checks, render, reconcile)
│   ├── norm_check.py      ← automated compliance checker against OGUC/NCh articles
│   ├── render_check.py    ← plan export verification + 3D render gate
│   ├── area_calc.py       ← area/surface computation from FreeCAD models
│   ├── norms/rules.json   ← machine-checkable thresholds + their provenance
│   └── scripts/           ← headless FreeCAD/Blender scripts (export_dxf.py, …)
├── sources/               ← input material per project: site surveys, topos, specs
│   └── <subject>/         ← one folder per reference subject, with SOURCES.md
├── projects/              ← all architecture projects live here
│   ├── <ProjectName>/
│   │   ├── README.md      ← project goal, site, program, status, norm compliance log
│   │   ├── plans/         ← FreeCAD files (.FCStd) — floor plans, sections, elevations
│   │   ├── model/         ← Blender files (.blend) — 3D model and renders
│   │   ├── exports/       ← generated output: DXF, PDF, IFC, renders
│   │   ├── specs/         ← EETT, material schedules, budgets
│   │   ├── calcs/         ← structural calculations, thermal analysis
│   │   ├── site.json      ← PRC limits, thermal/seismic zone — read by norm_check
│   │   └── attempts/      ← rejected approaches (gitignored, never committed)
│   └── ...
├── templates/             ← README.template.md, site.template.json
└── .claude/agents/        ← the eleven subagent definitions
```

`sources/` and `tools/` stay at the repo root, shared across all projects —
never nested under `projects/`.

## Units and coordinate convention

- All dimensions in plans and scripts are in **meters** for architecture,
  **centimeters** for construction details, **millimeters** for joinery/steel.
- Coordinate origin is the **northwest corner of the site** at ground level,
  with **+X east**, **+Y south**, **+Z up** — matching Chilean municipal
  plan convention.
- Levels are referenced to **NPT** (Nivel de Piso Terminado) and **NCR**
  (Nivel de Cota de Referencia) per OGUC.

## Two rules that cost this repo the most

- **A version is never a sibling folder.** Nest it as `projects/<Project>/v2/`.
  Never delete an old version — v2 may import from `v0/plans/`. See
  [docs/versioning.md](docs/versioning.md).
- **Never delete an attempt on your own judgment.** Only an explicit rejection
  from the user triggers cleanup, and the lesson gets recorded in the project
  README before the folder goes. See [docs/attempts.md](docs/attempts.md).

## Project README template

Every project README must contain at minimum:

```markdown
# <Project Name>

## Site
- Address / Rol:
- Comuna / PRC:
- Thermal zone (NCh 1079):
- Seismic zone (NCh 433):

## Program
- Building type:
- Floors / levels:
- Total built area (m²):
- Occupancy:

## Norm compliance log
| Norm | Article | Status | Verified by | Date |
|------|---------|--------|-------------|------|

## Rejected approaches
| Slug | What was tried | Why it failed (measured) |
|------|----------------|-------------------------|
```
