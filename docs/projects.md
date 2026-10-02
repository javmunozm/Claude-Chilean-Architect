# Project index

One row per project. Update it when a project is created, when its status
changes, and when a version is nested inside it.

| Project | Description | Comuna | Status | Versions |
|---------|-------------|--------|--------|----------|
| CasaPatioInterior | Vivienda unifamiliar 2 pisos con patio interior, 13,00 × 14,00 m (desde `sources/Test`) | por definir | `review` | rev. G (origen), rev. H (`plans/`), v2 (`v2/`), v3 (`v2/v3/`) |

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
mkdir -p projects/<Name>/{plans,model,exports,specs,calcs,attempts}
cp templates/README.template.md projects/<Name>/README.md
cp templates/site.template.json projects/<Name>/site.json
```

Then add a row above and brief `site-analyst`. See [commands.md](commands.md).

## Naming

Use a descriptive name in the form the project is actually called — `CasaValdivia`,
`EdificioSanMartin`, `AmpliacionLosAndes`. No dates and no version suffixes in the
folder name: versions nest inside the project as `v2/`, never as siblings. See
[versioning.md](versioning.md).
