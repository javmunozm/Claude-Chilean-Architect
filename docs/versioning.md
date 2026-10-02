# Versioning a project

## The rule

**Every version lives in `versions/`, one folder per version, side by side.** The
project root holds only the index, the site and that folder:

```
projects/CasaValdivia/
├── README.md              ← project index: the versions table and the lineage
├── site.json              ← the site, ONE file shared by every version
└── versions/
    ├── v0/                ← the original
    ├── v2/                ← descends from v0
    └── v3/                ← descends from v2
```

Not this:

```
projects/CasaValdivia_v2/        ← WRONG: sibling project, the relation is lost
projects/CasaValdivia/v2/v3/     ← WRONG: nested, every version buries the next
projects/CasaValdivia/v2/        ← WRONG: versions loose in the project root
```

Before 2026-10-03 this repo nested versions (`v2/v3/`). It was changed at the
user's request: nesting made paths grow with every version, hid newer versions
inside older ones, and recorded nothing the README table does not record better.
See [lessons.md](lessons.md).

## Inside a version

Every version has the same layout:

```
versions/vN/
├── README.md        what vN changes, why, and which version it DESCENDS FROM
├── source/          inputs written by hand or taken from documents (only if vN has its own)
├── scripts/         the macros that generate vN — vN's own copy
├── calcs/           measured or derived data: model_extract, plan_data, recintos, puertas
├── exports/
│   ├── <name>.pdf   the drawing set, at the root of exports
│   ├── model/       .FCStd, .blend, .obj/.mtl — the generated model
│   ├── drawings/    construction drawings: DXF per floor + their PNG previews
│   └── renders/     3D control views and presentation renders
├── specs/           EETT, schedules, budgets (when they exist)
└── attempts/        rejected approaches, never committed (docs/attempts.md)
```

**Scripts are per version on purpose.** Each version keeps the exact macros that
produced it, so the difference between `versions/v2/scripts/` and
`versions/v3/scripts/` is the record of how the method evolved (a stair rule, a door
policy). Shared logic that every version must use lives in `tools/` at the repo
root and is imported, never copied.

**`site.json` is one file at the project root.** The site does not change between
versions; a copy per version drifts (it happened: v3's copy came from v2's and lost
the Concepción fields that v0's had). If a version genuinely studies another site,
it carries its own `site.json` and its README says why.

## Lineage lives in the README, not in the path

The project `README.md` has the versions table:

| Version | Descends from | What changed and why |
|---------|---------------|----------------------|
| v0 | — | Original |
| v2 | v0 | … |
| v3 | v2 | … |

and each `versions/vN/README.md` repeats its parent in its first lines. A version
may read files of an earlier version by relative path (`../v0/source/plan.json`) —
reference a valid input, do not copy it.

## Never delete an old version

Even when vN fully supersedes it. The old version holds:

- Geometry or inputs that later versions still import.
- The compliance log showing which reviews passed and when.
- The record of why the design changed.

## Creating a new version

1. **Create the folder** with the standard layout:
   ```bash
   mkdir -p projects/<Name>/versions/vN/{scripts,calcs,exports/{model,drawings,renders},attempts}
   ```
2. **Copy the parent's scripts**, then change what this version changes:
   ```bash
   cp projects/<Name>/versions/<parent>/scripts/*.py projects/<Name>/versions/vN/scripts/
   ```
   Fix every path in them to `versions/vN/` and record each change in the README.
3. **Do not copy `site.json`.** All versions read `projects/<Name>/site.json`.
4. **Write `versions/vN/README.md`** from the template: what vN changes, why, and
   which version it descends from.
5. **Add the row to the project README** versions table.
6. **Re-run every review.** vN inherits none of its parent's verdicts.

## What a new version does not inherit

- **Compliance verdicts.** All must be re-run against the new geometry.
- **Calcs.** `calcs/model_extract.json` describes the parent's geometry. Regenerate.
- **Exports.** Regenerate them; `render_check.py` flags copied exports as STALE
  against the new model, which is exactly right.
