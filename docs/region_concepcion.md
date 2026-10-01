# Gran Concepción — regional norms register

Which instruments apply to a site in or near Concepción (Región del Biobío), where
each one lands in this repo, and **how far each has actually been verified**.

Compiled 2026-10-01. Read the status column before using anything here.

## Status of this register — read first

Every official source for these instruments (minvu.gob.cl, diariooficial.interior.gob.cl,
bcn.cl, ppda.mma.gob.cl) was **blocked by the network policy of the environment that
compiled this file**. Nothing here was read off an official text. What is recorded
is:

- **which instruments exist and govern what** — reliable enough to route work, and
  each row names the official document to open;
- **leads** — values taken from web-search summaries of secondary pages. A lead
  tells `site-analyst` what to look for. It is **not** a citation, and it must not
  be copied into `site.json` or `tools/norms/rules.json` as if it were (CORE
  DIRECTIVE 3 and 5; see [norms.md](norms.md#transcribing-a-threshold)).

Two search summaries for the same thermal limit disagreed with each other. One gave
an old-regime zone-5 wall value, the other a value for new zone E. That conflict is
the reason no number below is promoted to a threshold.

| Status | Meaning |
|--------|---------|
| `TRANSCRIBED` | read off the official text, cited, safe to enforce |
| `LEAD` | from a secondary source; confirm against the official text before use |
| `NOT STARTED` | instrument identified, nothing extracted yet |

## Comunas

Two different groupings matter, and they are not the same list:

| Comuna | PRMC (metropolitan plan) | PPDA Concepción Metropolitano |
|--------|:---:|:---:|
| Concepción | LEAD: yes | LEAD: yes |
| Talcahuano | LEAD: yes | LEAD: yes |
| Hualpén | LEAD: yes | LEAD: yes |
| San Pedro de la Paz | LEAD: yes | LEAD: yes |
| Chiguayante | LEAD: yes | LEAD: yes |
| Penco | LEAD: yes | LEAD: yes |
| Tomé | LEAD: yes | LEAD: yes |
| Coronel | LEAD: yes | LEAD: yes |
| Lota | LEAD: yes | LEAD: yes |
| Hualqui | LEAD: yes | LEAD: yes |
| Santa Juana | LEAD: yes | LEAD: **not listed** |

Sources of the leads: the PRMC ordinance draft (eae.mma.gob.cl), and search
summaries of the PPDA decree and of the 2015 saturated-zone declaration (DS 15/2015
MMA). Confirm both lists against the official texts.

## Instruments

| # | Instrument | Governs | Lands in | Owner | Status |
|---|-----------|---------|----------|-------|--------|
| 1 | **OGUC Art. 4.1.10, as replaced by DS N°15/2024 (MINVU)** | Thermal envelope of residential buildings: max U / min R by element, surface and interstitial condensation, air infiltration, ventilation. **9 thermal zones A–I** replacing the old 7 zones | `rules.json` → `thermal_zones`; `site.json` → `thermal_zone` | `thermal-reviewer`, `site-analyst` | LEAD |
| 2 | **PPDA Concepción Metropolitano — DS N°6/2018 (MMA)** | Air-quality plan. Its new-housing article sets an envelope transmittance standard and an air-infiltration standard | `rules.json` → `ppda_concepcion_metropolitano`; `site.json` → `ppda` | `thermal-reviewer` | LEAD |
| 3 | **NCh 433 Of.1996 Mod.2009 + DS N°61/2011 (MINVU)** | Seismic zone by comuna (NCh 433 Table 4.1 governs for regions IV–IX and RM); seismic soil class from Vs30 plus complementary tests | `site.json` → `seismic.zone`, `seismic.soil_type` | `structural-reviewer`, `site-analyst` | LEAD |
| 4 | **PRMC — Plan Regulador Metropolitano de Concepción** | Metropolitan land use and **risk areas**, including tsunami flood areas, over the comunal PRCs | `site.json` → `prm`, `risk_designations` | `site-analyst` | LEAD |
| 5 | **PRC comunal + Certificado de Informaciones Previas** | Site zoning, setbacks, height, occupancy, FAR | `site.json` → `prc`, `prc_limits` | `site-analyst` | per site — never copied |
| 6 | **OGUC Título 2 — áreas de riesgo** (the OGUC article that lets planning instruments define risk areas, believed to be Art. 2.1.17) | Conditions for building inside a risk area | project README compliance log | `site-analyst` | NOT STARTED — article number unconfirmed |

### 1 — Thermal: DS 15/2024 replaces the old Art. 4.1.10 table

- **LEAD:** DS 15 was published in the Diario Oficial on 2024-05-27 (CVE 2494861),
  and its requirements became mandatory on **2025-11-28**. Source: MINVU DITEC
  presentations, as reported in search summaries.
- **LEAD:** comuna **Concepción → zone E**. The other comunas are not yet looked up.
- **What changed for this repo:** `rules.json` used to model zones A–G. It now
  has columns A–I and a `door` element. Every value is still `null` and
  `_status: UNVERIFIED`.
- **Official sources to transcribe from:** the Diario Oficial publication of
  DS 15/2024, and MINVU's *Zonificación Térmica* table (minvu.gob.cl, "ZONIFICACION-TERMICA").

### 2 — PPDA Concepción Metropolitano

- **LEAD:** "vivienda nueva" means a dwelling whose permit or anteproyecto is
  filed 12 months or more after the plan entered into force. Those dwellings must
  meet a maximum envelope U and an air-infiltration class (decree article 25,
  per search summary). The plan has been under revision since 2025 (Res. Ex.
  N°7509 MMA).
- **Not known:** whether the PPDA standard is stricter than post-DS 15 Art. 4.1.10
  for every element in the zone that applies, or whether DS 15 superseded it.
  Answer this from the two texts, not by assumption. Until it is answered, both
  rules stay in `rules.json`, and the stricter limit governs only once both are
  transcribed.
- **Official sources:** ppda.mma.gob.cl (`Decreto-6_-PPDA-Concepcion-Metropolitano.pdf`),
  and BCN Ley Chile idNorma 1140121.

### 3 — Seismic

- **LEAD:** Concepción and Talcahuano are in **seismic zone 3**. The zones of the
  other comunas are not yet looked up.
- DS 61 classifies soil from **Vs30** plus complementary parameters (N-SPT, qu,
  Su, RQD), with categories A–F per the search summary. **Soil class is a property
  of the site, not of the comuna.** It comes from a geotechnical study, never
  from a map or a neighbour's report.
- Microzonation studies of Concepción exist (e.g. *Estudio preliminar de
  microzonificación sísmica de Concepción basado en microvibraciones, geología y
  patrones de daño*, SciELO Chile, 2012). They are context for the geotechnical
  engineer, not a substitute for the study.
- This repo has no structural solver. A seismic verdict stays INCONCLUSIVE with a
  handoff to a calculista ([agents.md](agents.md)).

### 4 — PRMC and risk areas

- **LEAD:** the PRMC in force dates from 2003 (Res. N°171 GORE Biobío, 2002-12-05,
  published 2003-01-28). A modification is in progress. Its risk studies cover
  floods, landslides, tsunami, coastal erosion and wildfire; a 2026 study for the
  modification puts more than 90% of the province at wildfire risk.
- **LEAD:** the PRMC ordinance maps **tsunami flood risk areas** in two levels
  ("alto" and "medio").
- What to do: for every site, read the PRMC risk plan at the parcel and record
  the result in `site.json → risk_designations`, with the plan sheet as `source`.
  A site inside a risk area triggers the OGUC risk-area procedure (row 6) before
  programming starts.

## Procedure for a new site near Concepción

1. `site-analyst` puts the Certificado de Informaciones Previas, and the PRMC
   sheet covering the parcel, in `sources/<Project>/`.
2. Fill in `site.json`: `comuna`, `prm`, `prc`, `prc_limits`, `ppda` (only if the
   comuna is in the PPDA list, confirmed), `thermal_zone` (from the DS 15 table),
   `seismic.zone` (from NCh 433 Table 4.1), `risk_designations`. Every value cites
   its document; anything unconfirmed stays `null`.
3. `seismic.soil_type` stays `null` until a geotechnical study exists.
4. Run `tools/norm_check.py --site`. Rules gated on `ppda` report SKIP outside the
   PPDA zone. Thermal rules report UNVERIFIED until `rules.json` is transcribed.
5. To move a row of this register from LEAD to TRANSCRIBED, follow
   [norms.md § Transcribing a threshold](norms.md#transcribing-a-threshold) and
   update the status here.
