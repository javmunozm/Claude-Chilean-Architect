# The subagents

Eleven agents, defined in `.claude/agents/`. Each owns a domain of Chilean
building regulation or a stage of production, and each is briefed to cite the
article behind every verdict.

## Roster

| Agent | Domain | Key norms |
|-------|--------|-----------|
| `site-analyst` | Terrain, orientation, site constraints, PRC compliance | OGUC Art. 2.1, PRC |
| `program-architect` | Rooms, areas, circulation, zoning | OGUC Art. 4.1, NCh 1079 |
| `plan-drafter` | FreeCAD plans, sections, elevations, details | — |
| `structural-reviewer` | Structural system, seismic verification | NCh 433, 3171, 2369 |
| `thermal-reviewer` | Envelope, insulation, condensation | NCh 853, OGUC 4.1.10 |
| `fire-safety-reviewer` | Fire resistance, egress, compartments | OGUC Art. 4.3, NCh 935 |
| `accessibility-reviewer` | Universal accessibility | OGUC 4.1.7, Ley 20.422 |
| `installations-reviewer` | Electrical, plumbing, gas | NCh Elec. 4/2003, NCh 2485 |
| `3d-modeler` | Blender modeling and rendering | — |
| `form-auditor` | Auditing real 3D form against intent | — |
| `spec-writer` | EETT, schedules, budgets | — |

## Handoff order

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

The order encodes dependencies. site-analyst must precede program-architect
because the program has to fit inside PRC ceilings. plan-drafter precedes every
reviewer because there is nothing to review until geometry exists. spec-writer
comes last because specifying an uncleared design produces documentation for a
building that cannot be permitted.

The four reviewers between plan-drafter and 3d-modeler are ordered by how
expensive their findings are to absorb: a structural change invalidates more
downstream work than an accessibility fix, so it surfaces first.

## Briefing an agent

Give it four things:

1. **The project path.** `projects/<Name>/` — it reads `site.json` and `README.md`
   from there.
2. **What changed since it last ran**, if anything. Reviewers should not re-derive
   a whole project to check one altered wall.
3. **The specific question**, if you have one. "Does the corridor comply?" gets a
   better answer than "review this."
4. **Whether it may edit.** Default is propose-only. CORE DIRECTIVE 2 means no
   agent changes production files without approval.

## Reading a verdict

Every agent reports in the same shape:

```
FINDINGS   — what was measured, with numbers and units
CITATIONS  — norm + article behind each verdict
VERDICT    — COMPLIANT / NON-COMPLIANT / INCONCLUSIVE (+ why)
HANDOFF    — what the next agent needs to know
```

**INCONCLUSIVE is a real answer, not a failure.** It is the correct output when a
threshold has not been transcribed from the official text, when a verdict needs a
structural calculation this repo cannot run, or when the model lacks the geometry
to measure. An agent that converts an unmeasured question into a confident PASS
has broken CORE DIRECTIVE 3, which is a worse outcome than an honest gap.

Expect INCONCLUSIVE verdicts frequently at present: `tools/norms/rules.json`
ships with every threshold unverified. See [norms.md](norms.md).

## Who overrules whom on a question of fact

`form-auditor` outranks renders and drawings. When `3d-modeler` produces an image
of a generous-looking room and `form-auditor` measures 2.10 m of clear height, the
measurement wins. A render is not a measurement — it can hide a missing wall
behind a camera angle or flatter a proportion with a lens choice.

Reviewers outrank the program. `program-architect` states intent; the extract from
`area_calc.py` states what exists. Where they differ, the extract is what will be
built, and the difference is itself a finding.

## Cross-cutting findings

Some findings belong to two agents. A drain cored through a shear wall is both a
plumbing route and a structural penetration; an unsealed duct through a fire
compartment is both an installations detail and a life-safety breach.

The agent that spots it raises it to both, and the structural or fire agent rules
on it. Neither silently assumes the other noticed.
