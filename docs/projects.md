# Project index

One row per project. Update it when a project is created, when its status
changes, and when a version is added to its `versions/` folder.

| Project | Description | Comuna | Status | Versions |
|---------|-------------|--------|--------|----------|
| CasaPatioInterior | Vivienda unifamiliar 2 pisos con patio interior, 13,00 × 14,00 m (desde `sources/Test`) | por definir | `review` | `versions/v0` (rev. H; rev. G de origen en `v0/source/`), `versions/v2` (← v0), `versions/v3` (← v2), `versions/v4` (← v3, juego de 5 láminas), `versions/v5` (← v4, + aguas lluvias, terminaciones, detalles, memoria de cálculo, EETT) |

## Status values

| Status | Meaning |
|--------|---------|
| `site` | site-analyst working; envelope not yet fixed |
| `program` | program-architect working; no geometry yet |
| `drafting` | plan-drafter authoring geometry |
| `review` | one or more reviewers working through findings |
| `modeling` | 3d-modeler building the 3D model and renders |
| `audit` | form-auditor reconciling built form against intent |
| `specs` | spec-writer producing EETT and budget |
| `complete` | all stages done, compliance log has no open items |
| `paused` | deliberately halted; the README says why |

A project sitting in `review` with open NON-COMPLIANT findings is not `complete`,
however finished the drawings look.

## Starting a project

```bash
mkdir -p projects/<Name>/versions/v0/{source,scripts,calcs,specs,attempts,exports/{model,drawings,renders}}
cp templates/README.template.md projects/<Name>/versions/v0/README.md
cp templates/site.template.json projects/<Name>/site.json
# projects/<Name>/README.md: short index with the versions table (docs/versioning.md)
```

Then add a row above and brief `site-analyst`. See [commands.md](commands.md).

## Naming

Use a descriptive name in the form the project is actually called — `CasaValdivia`,
`EdificioSanMartin`, `AmpliacionLosAndes`. No dates and no version suffixes in the
folder name: versions go side by side in `versions/` (`v0/`, `v2/`, `v3/`…). See
[versioning.md](versioning.md).
