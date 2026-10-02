# Repository structure and conventions

## The shape of the repo

```
ArquiCL/
├── baseSystemCad.md   ← index, CORE DIRECTIVE, doc pointers
├── docs/              ← this documentation
├── tools/             ← shared tooling (norm check, render gate, area calc,
│                        roof geometry, doors, 3D verification)
│   └── norms/         ← rules.json: machine-checkable norm thresholds
├── sources/           ← input material per subject, each with SOURCES.md
├── templates/         ← reusable templates for new projects
├── projects/          ← one folder per building or intervention
└── .claude/agents/    ← the eleven subagent definitions
```

`sources/` and `tools/` stay at the root, shared across all projects. They are
never nested under `projects/`, because the moment a tool is copied into a project
it stops receiving fixes.

## A project

```
projects/<Name>/
├── README.md          ← project index: versions table with lineage ("descends from")
├── site.json          ← PRC limits, thermal zone, seismic zone (machine-read, ONE per project)
└── versions/
    └── vN/            ← one folder per version, side by side (docs/versioning.md)
        ├── README.md  ← goal, program, status, compliance log, descends from
        ├── source/    ← inputs written by hand or taken from documents
        ├── scripts/   ← this version's own generation macros (FreeCAD, DXF, OBJ…)
        ├── calcs/     ← model_extract.json, plan_data, recintos, puertas, calcs
        ├── exports/   ← everything generated
        │   ├── <name>.pdf   drawing set
        │   ├── model/       .FCStd, .blend, .obj/.mtl
        │   ├── drawings/    construction drawings: DXF + PNG previews
        │   └── renders/     3D views and renders
        ├── specs/     ← EETT, schedules, budgets
        └── attempts/  ← rejected approaches (never committed)
```

### `site.json` is load-bearing

It is not documentation — `tools/norm_check.py` reads it directly. It carries the
per-site limits that cannot be national constants: PRC ceilings, the NCh 1079
thermal zone, the NCh 433 seismic zone and soil type.

An absent or null value means a real consequence: rules that depend on it report
SKIP or UNVERIFIED rather than passing. That is the intended behaviour. See
[norms.md](norms.md) for the two-kinds-of-limit distinction.

## The pipeline

```
sources/            site surveys, PRC certificates, topography
    │
    ▼  site-analyst
site.json           the regulatory and physical envelope
    │
    ▼  program-architect
README.md           the dimensioned program, inside those ceilings
    │
    ▼  plan-drafter
scripts/ → exports/model/*.FCStd   Arch/BIM geometry
    │
    ├──▼  area_calc.py  →  calcs/model_extract.json  →  norm_check.py
    │
    ▼  3d-modeler
exports/model/*.blend   3D model
    │
    ▼  (exports)
exports/            DXF, PDF, IFC, PNG  →  render_check.py
    │
    ▼  form-auditor
                    measured reality, reconciled against intent
    │
    ▼  spec-writer
specs/              EETT, schedules, budget
```

Geometry flows one way: plans are authored in FreeCAD and consumed by Blender,
never the reverse. A 3D model edited independently of the plans is a model that
will disagree with them, and the disagreement surfaces at the worst moment.

## Naming Arch Spaces

This convention is functional, not cosmetic. `tools/area_calc.py` tags spaces by
label, and those tags decide which norm rules apply to them. A misnamed space
silently escapes its rules — it reports as compliant because nothing was checked.

| Label contains | Tags applied | Rules that then apply |
|----------------|--------------|----------------------|
| dormitorio, estar, comedor, living, cocina, oficina, sala | `habitable` | clear height, min width |
| dormitorio principal, master | `dormitorio_principal` | minimum bedroom area |
| baño, bano, bath, wc, aseo | `wet` | ventilation |
| pasillo, corridor, hall, circulación | `corridor`, `circulation` | corridor width |
| accesible, accessible | `accessible_bathroom` | turning circle |

Use Spanish room names as an architect would. `Dormitorio Principal`, `Estar`,
`Pasillo`, `Baño Accesible`. A space called `Room001` gets no tags and no checks.

## Units and coordinates

- **Metres** for architecture, **centimetres** for construction details,
  **millimetres** for joinery and steel.
- FreeCAD works internally in millimetres; `area_calc.py` converts to metres on
  the way out. Model in millimetres, read results in metres.
- Origin: **northwest corner of the site at ground level**, **+X east**,
  **+Y south**, **+Z up** — matching Chilean municipal plan convention.
- Levels referenced to **NPT** (Nivel de Piso Terminado) and **NCR** (Nivel de
  Cota de Referencia) per OGUC.

A 1000× unit slip is the most dangerous error in this repo: the numbers stay
plausible in isolation. form-auditor sanity-checks magnitudes for exactly this.

## Build with Arch objects

Use Arch Wall, Space, Window, Door, Slab, Structure — not raw Part solids.
`area_calc.py` reads the Arch object graph via `IfcType`. Raw primitives are
invisible to it, and anything invisible to the extractor is never checked by the
norm checker.

An Arch Space must be **closed** to report a correct area. An unclosed space still
reports *an* area; it is simply wrong. The extract's `rectangularity` field exists
to surface this — investigate anything below 0.95.
