# Chilean building norms — index and responsibility map

## Status of this index — read first

This file records **which norm governs what** and **which agent owns it**. That
mapping is reliable.

What it does **not** contain is a transcribed table of numeric limits, and that
absence is deliberate. Under CORE DIRECTIVE 3 and 5, a threshold is usable only
when it has been read off the official text and cited. A remembered value that
looks right is exactly the failure mode the directive exists to prevent: it would
be copied into `tools/norms/rules.json`, stamped COMPLIANT on a real project, and
never questioned again.

So `tools/norms/rules.json` ships with every threshold marked `UNVERIFIED`, and
`tools/norm_check.py` refuses to return PASS for any rule in that state. The
system reports INCONCLUSIVE until someone does the transcription. See
[Transcribing a threshold](#transcribing-a-threshold).

## The norms

### OGUC — Ordenanza General de Urbanismo y Construcciones

The master regulation. Most day-to-day architectural compliance lives here.

| Article | Scope | Owning agent |
|---------|-------|--------------|
| Art. 2.1 | Urban planning, site definitions | `site-analyst` |
| Art. 4.1 | Habitability — areas, dimensions, heights, ventilation | `program-architect` |
| Art. 4.1.7 | Universal accessibility | `accessibility-reviewer` |
| Art. 4.1.10 | Reglamentación térmica — envelope U-values | `thermal-reviewer` |
| Art. 4.2 | Stairs, ramps, circulation elements | `accessibility-reviewer`, `fire-safety-reviewer` |
| Art. 4.3 | Fire safety — resistance, egress, compartments | `fire-safety-reviewer` |

### NCh — Normas Chilenas

| Norm | Scope | Owning agent |
|------|-------|--------------|
| NCh 433 | Seismic design of buildings | `structural-reviewer` |
| NCh 3171 | Seismic design of non-structural components | `structural-reviewer` |
| NCh 2369 | Seismic design of industrial structures | `structural-reviewer` |
| NCh 1079 | Habitability — thermal zoning of Chile (zones A–G) | `site-analyst`, `thermal-reviewer` |
| NCh 853 | Thermal conditioning — envelope resistance calculation | `thermal-reviewer` |
| NCh 935 | Fire resistance classification and test method | `fire-safety-reviewer` |
| NCh Elec. 4/2003 | Electrical installations, low voltage | `installations-reviewer` |
| NCh 2485 | Gas installations | `installations-reviewer` |

### Law and municipal instruments

| Instrument | Scope | Owning agent |
|------------|-------|--------------|
| Ley 20.422 | Disability rights, universal accessibility | `accessibility-reviewer` |
| PRC comunal | Zoning, setbacks, height, occupancy, FAR | `site-analyst` |
| Certificado de Informaciones Previas | The binding per-site statement of PRC limits | `site-analyst` |

## Two kinds of limit

**National limits** (OGUC articles, NCh values) are the same everywhere in Chile
and belong in `tools/norms/rules.json`, transcribed once.

**Per-site limits** (PRC occupancy ratio, constructibilidad, height, setbacks)
change by comuna *and* by zone within a comuna. They belong in each project's
`site.json`, sourced from that site's certificate. A PRC limit carried over from
another project is simply wrong — Providencia's numbers are not Valparaíso's.

`norm_check.py` handles the distinction: rules marked `"source": "PROJECT"` take
their threshold from `site.json`, and a threshold supplied that way counts as
sourced, because the certificate is the citation.

## Zone-dependent limits

Thermal limits are selected by the NCh 1079 zone (A–G) of the comuna. The zone is
not a property of the building and cannot be inferred from the plans — it comes
from `site.json`, written there by `site-analyst`. A U-value that passes in zone A
fails in zone G, so a missing zone means no thermal verdict at all.

Seismic design likewise depends on the NCh 433 seismic zone and soil type, both
site properties recorded in `site.json`.

## Transcribing a threshold

To move a rule from UNVERIFIED to enforceable:

1. Open the **official text** of the cited article. Not a summary, not a blog, not
   recollection.
2. Confirm the article number is current. OGUC is amended; a superseded article
   number produces a citation that cannot be checked.
3. Set `threshold` in `tools/norms/rules.json` to the value in the text.
4. Replace `"source": "UNVERIFIED"` with a real citation, e.g.
   `"source": "OGUC Art. 4.1.2, official text, transcribed 2026-09-18"`.
5. Re-run the checker. The rule now yields PASS/FAIL instead of UNVERIFIED.
6. Record the transcription in the project's compliance log.

For the thermal table, also set `thermal_zones._status` away from `"UNVERIFIED"`
once every zone column is filled.

## What the automated checker can and cannot do

`tools/norm_check.py` evaluates **dimensional** rules against measured geometry:
clear heights, areas, widths, slopes, U-values. That is a genuine but narrow slice.

It cannot judge: structural adequacy (needs analysis), fire strategy (needs
occupancy reasoning), spatial quality, or anything requiring engineering judgment.
A clean checker run means "the dimensional rules encoded here were satisfied" —
never "the project complies." The reviewer agents cover the rest, and their
verdicts are the ones that matter for a permit.
