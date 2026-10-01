# Attempts and the record-then-delete procedure

## What `attempts/` is for

Every project has one:

```
projects/<Name>/attempts/
├── patio-central/
├── escalera-exterior/
└── techo-mariposa/
```

One folder per approach that was explored and set aside. They hold work in
progress: a layout that might not survive, a structural idea being tested, a roof
form under consideration. Nothing in `attempts/` is committed.

Exploring freely matters. An architect who only draws what will certainly work
draws very little.

## The rule that costs this repo the most

**Never delete an attempt on your own judgment.**

Not when it looks abandoned. Not when it is clearly worse than what replaced it.
Not when tidying. Not when the user says "clean this up" without naming the
attempt.

Only an **explicit rejection from the user** triggers cleanup — the user saying,
of a specific attempt, that it is rejected and can go.

## Why

An attempt that looks abandoned may be the one the user is about to return to,
and the reason it was set aside may be the most valuable thing in the project. A
failed approach carries information a successful one does not: it marks a path
already explored, so nobody spends a week rediscovering why the patio scheme does
not work with the rasante.

Deleting it silently destroys that, and the loss is invisible — nobody knows what
is missing until they repeat the work.

## The procedure

When the user explicitly rejects an attempt:

### 1. Record the lesson first

Before anything is deleted, add a row to the project README:

```markdown
## Rejected approaches

| Slug | What was tried | Why it failed (measured) |
|------|----------------|--------------------------|
| patio-central | 4×4 m central patio, single storey around it | Left 38.2 m² of usable area against a 45 m² program requirement — measured via area_calc.py 2026-09-18 |
```

**"Why it failed" carries a measurement or a citation.** "Didn't work" and "user
didn't like it" record nothing. What failed, by how much, against which
requirement — that is what stops the approach being retried.

If the reason is genuinely a preference rather than a failure, say that: "user
preferred the linear scheme; no norm or area conflict found." An honest preference
is useful; a fabricated technical reason is not.

### 2. Consider whether it belongs in lessons.md

If the failure taught something that generalises past this project — a norm
interaction, a tool behaviour, a recurring geometric trap — write it up in
[lessons.md](lessons.md) as well. The project README records what happened here;
`lessons.md` records what to carry forward.

### 3. Then delete

```bash
rm -rf projects/<Name>/attempts/<slug>/
```

Only after steps 1 and 2. The record must exist before the evidence goes.

## Do not commit attempts

`attempts/` is gitignored. It holds exploratory work that would otherwise bury the
real history under dead ends. The *record* of a rejected attempt lives in the
README, which is committed; the working files do not.

## When the user says "clean up"

Ask which attempts. A general instruction to tidy is not an explicit rejection of
any particular approach, and this is precisely the case the rule exists for. A
short clarifying question costs a sentence; a wrong deletion costs work that
cannot be recovered.
