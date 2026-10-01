# Versioning a project

## The rule

**A version is never a sibling folder.** It nests inside the project:

```
projects/CasaValdivia/          ← v0, the original, stays where it is
├── README.md
├── plans/
├── model/
└── v2/                         ← the new version, nested
    ├── README.md
    ├── plans/
    ├── model/
    └── exports/
```

Not this:

```
projects/CasaValdivia/
projects/CasaValdivia_v2/       ← WRONG
projects/CasaValdivia_final/    ← WRONG
projects/CasaValdivia_nuevo/    ← WRONG
```

## Why

Sibling folders lose the relationship. Six months on, nobody can tell whether
`CasaValdivia_final` supersedes `CasaValdivia_v2` or was abandoned before it, and
the folder names stop being informative exactly when the history matters.

Nesting keeps the lineage explicit and keeps `v0` reachable from inside `v2` —
which matters because **v2 may import from `v0/plans/`**. A detail drawn once and
still valid should be referenced, not redrawn. Redrawing it introduces a second
source of truth that will drift.

## Never delete an old version

Even when v2 fully supersedes v0. The old version holds:

- Geometry that v2 still imports.
- The compliance log showing which reviews passed and when.
- The record of why the design changed.

Deleting it converts a documented decision into a mystery. Storage is cheaper
than re-deriving a year of decisions.

## The move procedure

Creating v2 from an existing project:

1. **Create the nested folder** with the standard project layout:
   ```bash
   mkdir -p projects/<Name>/v2/{plans,model,exports,specs,calcs,attempts}
   ```
2. **Copy, do not move**, what v2 starts from. v0 stays intact and working:
   ```bash
   cp projects/<Name>/plans/<model>.FCStd projects/<Name>/v2/plans/
   ```
3. **Copy `site.json` unchanged.** The site did not change — the same PRC limits,
   thermal zone and seismic zone still govern. Re-deriving them invites a
   transcription error into a version that had them right.
4. **Write `v2/README.md`** from the template, and state in it **what v2 changes
   and why**. This is the field people actually read later.
5. **Note the version in the parent README** so the top level lists its versions.
6. **Re-run every review.** A v2 plan inherits none of v0's verdicts. Geometry
   changed, so every dimensional check is stale — the compliance log starts empty.

## What v2 does not inherit

- **Compliance verdicts.** All of them must be re-run against the new geometry.
- **The model extract.** `calcs/model_extract.json` describes v0's geometry.
   Regenerate it, do not copy it.
- **Exports.** `render_check.py` will flag copied exports as STALE against the new
  model, which is exactly right.

## Versions deeper than v2

Keep nesting: `projects/<Name>/v2/v3/`. It looks odd and it is correct — the
nesting shows that v3 descends from v2 rather than from v0, which is information a
flat `v3` folder would lose.

If nesting becomes genuinely unwieldy past three or four levels, that is worth
raising with the user rather than flattening it unilaterally. The flattening would
destroy the lineage this convention exists to preserve.
