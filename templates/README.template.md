# <Project Name>

One or two sentences: what this project is and what it is for.

## Site

- **Address / Rol:**
- **Comuna / PRC:**
- **Thermal zone (NCh 1079):**
- **Seismic zone (NCh 433):**

> Machine-readable values live in `site.json`, which `tools/norm_check.py` reads.
> Keep the two consistent — if they disagree, `site.json` is what actually governs
> the compliance run.

## Program

- **Building type:**
- **Floors / levels:**
- **Total built area (m²):**
- **Occupancy:**

### Room schedule

| Space | Area (m²) target | Area (m²) measured | Clear height (m) | Notes |
|-------|------------------|--------------------|------------------|-------|

> "Target" is program-architect's intent. "Measured" comes from
> `tools/area_calc.py` once geometry exists. They will differ; the difference is
> a finding, not an error to be quietly edited away.

## Area accounting

| Item | Allowed (PRC) | Designed | Source of limit |
|------|---------------|----------|-----------------|
| Occupancy ratio | | | |
| Constructibilidad (FAR) | | | |
| Maximum height | | | |

## Norm compliance log

| Norm | Article | Status | Verified by | Date |
|------|---------|--------|-------------|------|

> Status is COMPLIANT / NON-COMPLIANT / INCONCLUSIVE. INCONCLUSIVE is a real
> entry — record it rather than leaving the row blank, because a blank row is
> indistinguishable from a check nobody ran.

## Rejected approaches

| Slug | What was tried | Why it failed (measured) |
|------|----------------|--------------------------|

> Filled in **before** an attempt folder is deleted, and only on the user's
> explicit rejection. "Why it failed" carries a number or a citation. See
> `docs/attempts.md`.

## Versions

This file is `versions/vN/README.md`. **Descends from:** — (v0) / `vM`

| Version | Path | Descends from | What changed and why |
|---------|------|---------------|----------------------|
| v0 | `versions/v0/` | — | Original |

> Versions live side by side in `projects/<Name>/versions/`, never nested. The
> project README carries this table for all versions. See `docs/versioning.md`.

## Status

`site` / `program` / `drafting` / `review` / `modeling` / `audit` / `specs` /
`complete` / `paused`
