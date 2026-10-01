#!/usr/bin/env python3
"""Automated compliance checker against OGUC / NCh articles.

Reads a project model extract (JSON) and evaluates it against tools/norms/rules.json.
Every verdict cites the article it came from.

A rule whose threshold has not been transcribed from the official text reports
UNVERIFIED, never PASS. An unverified rule is a blocking result: the checker
exits non-zero, because CORE DIRECTIVE 3 forbids asserting compliance that was
not measured.

Usage:
    python tools/norm_check.py projects/<Name>/calcs/model_extract.json
    python tools/norm_check.py <extract.json> --site projects/<Name>/site.json
    python tools/norm_check.py <extract.json> --json      # machine-readable
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RULES_PATH = REPO / "tools" / "norms" / "rules.json"

PASS, FAIL, UNVERIFIED, SKIP = "PASS", "FAIL", "UNVERIFIED", "SKIP"


class Result:
    def __init__(self, rule, status, subject, detail, measured=None):
        self.rule = rule
        self.status = status
        self.subject = subject
        self.detail = detail
        self.measured = measured

    def as_dict(self):
        return {
            "rule_id": self.rule["id"],
            "norm": self.rule["norm"],
            "article": self.rule["article"],
            "status": self.status,
            "subject": self.subject,
            "measured": self.measured,
            "threshold": self.rule.get("threshold"),
            "detail": self.detail,
        }


def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def matches(entity, rule):
    """Does this entity fall under the rule's applies_to list?"""
    tags = set(entity.get("tags", []))
    kind = entity.get("kind")
    if kind:
        tags.add(kind)
    return bool(tags & set(rule["applies_to"]))


def unverified_reason(rule):
    """A threshold is usable only if it was transcribed from the official text.

    A remembered number that looks plausible is exactly what CORE DIRECTIVE 3
    forbids, so a rule still marked UNVERIFIED yields no verdict even when it
    carries a value.
    """
    if rule.get("threshold") is None and rule.get("source") != "PROJECT":
        return "threshold not transcribed from the official article"
    if rule.get("source") == "UNVERIFIED":
        return ("threshold present but never checked against the official text "
                "of %s - transcribe it and set source" % rule["article"])
    if rule.get("source") == "PROJECT" and rule.get("threshold") is None:
        return ("project-specific limit not supplied; set it in the project's "
                "site.json from the PRC certificate")
    return None


def check_min(entity, rule):
    field, threshold = rule["field"], rule.get("threshold")
    name = entity.get("name", "<unnamed>")
    reason = unverified_reason(rule)
    if reason:
        return Result(rule, UNVERIFIED, name, reason,
                      entity.get(field))
    if field not in entity:
        return Result(rule, SKIP, name,
                      "model extract has no '%s' for this entity" % field)
    value = entity[field]
    ok = value >= threshold - 1e-9
    return Result(rule, PASS if ok else FAIL, name,
                  "%s=%.3f vs minimum %.3f" % (field, value, threshold), value)


def check_max(entity, rule):
    field, threshold = rule["field"], rule.get("threshold")
    name = entity.get("name", "<unnamed>")
    reason = unverified_reason(rule)
    if reason:
        return Result(rule, UNVERIFIED, name, reason,
                      entity.get(field))
    if field not in entity:
        return Result(rule, SKIP, name,
                      "model extract has no '%s' for this entity" % field)
    value = entity[field]
    ok = value <= threshold + 1e-9
    return Result(rule, PASS if ok else FAIL, name,
                  "%s=%.3f vs maximum %.3f" % (field, value, threshold), value)


def check_max_by_zone(entity, rule, rules_doc, zone):
    name = entity.get("name", "<unnamed>")
    table = rules_doc.get(rule["threshold_table"], {})
    # Sin valor medido no hay nada que juzgar: es un dato ausente (SKIP), no un
    # umbral sin verificar. Se comprueba antes que el estado de la tabla para no
    # inundar el informe con una fila por cada ventana sin U declarado.
    if rule["field"] not in entity:
        return Result(rule, SKIP, name,
                      "el extract no trae '%s' para esta entidad" % rule["field"])
    if table.get("_status") == "UNVERIFIED":
        return Result(rule, UNVERIFIED, name,
                      "%s table not transcribed from %s; cannot evaluate"
                      % (rule["threshold_table"], rule["article"]))
    if zone is None:
        return Result(rule, SKIP, name,
                      "project thermal zone not declared in site.json")
    limits = table.get(zone, {})
    kind = entity.get("kind")
    threshold = limits.get(kind)
    if threshold is None:
        return Result(rule, UNVERIFIED, name,
                      "no U-value limit recorded for kind '%s' in zone %s" % (kind, zone))
    if rule["field"] not in entity:
        return Result(rule, SKIP, name,
                      "model extract has no '%s'" % rule["field"])
    value = entity[rule["field"]]
    ok = value <= threshold + 1e-9
    return Result(rule, PASS if ok else FAIL, name,
                  "U=%.3f vs max %.3f (zone %s)" % (value, threshold, zone), value)


def check_max_by_kind(entity, rule, rules_doc):
    """Limit table indexed by element kind only (no zone), e.g. the PPDA standard."""
    name = entity.get("name", "<unnamed>")
    if rule["field"] not in entity:
        return Result(rule, SKIP, name,
                      "el extract no trae '%s' para esta entidad" % rule["field"])
    table = rules_doc.get(rule["threshold_table"], {})
    if table.get("_status") == "UNVERIFIED":
        return Result(rule, UNVERIFIED, name,
                      "%s table not transcribed from %s; cannot evaluate"
                      % (rule["threshold_table"], rule["article"]),
                      entity.get(rule["field"]))
    kind = entity.get("kind")
    threshold = table.get(kind)
    if threshold is None:
        return Result(rule, UNVERIFIED, name,
                      "no limit recorded for kind '%s' in %s" % (kind, rule["threshold_table"]))
    value = entity[rule["field"]]
    ok = value <= threshold + 1e-9
    return Result(rule, PASS if ok else FAIL, name,
                  "U=%.3f vs max %.3f" % (value, threshold), value)


def site_condition_unmet(rule, site):
    """A rule gated on a site property (e.g. the PPDA zone) applies only when
    site.json declares that property. Returns the SKIP reason, or None."""
    cond = rule.get("site_condition")
    if not cond:
        return None
    value = (site or {}).get(cond["field"])
    if value is None:
        return ("applies only when site.json declares %s = %r; it is not declared"
                % (cond["field"], cond["equals"]))
    if value != cond["equals"]:
        return ("applies only when site.json declares %s = %r; site has %r"
                % (cond["field"], cond["equals"], value))
    return None


def apply_site_thresholds(rules_doc, site):
    """PRC limits are per-comuna: pull them from the project's site.json."""
    prc = (site or {}).get("prc_limits", {})
    for rule in rules_doc["rules"]:
        if rule.get("source") == "PROJECT" and rule["field"] in prc:
            rule["threshold"] = prc[rule["field"]]
            # Sourced from the project's PRC certificate: a real citation, so
            # this rule is now evaluable.
            rule["source"] = "site.json (PRC certificate)"
            rule["_threshold_from"] = "site.json"


def run(extract, rules_doc, site=None):
    zone = (site or {}).get("thermal_zone")
    entities = extract.get("entities", [])
    results = []
    for rule in rules_doc["rules"]:
        gated = site_condition_unmet(rule, site)
        if gated:
            results.append(Result(rule, SKIP, "-", gated))
            continue
        targets = [e for e in entities if matches(e, rule)]
        if not targets:
            results.append(Result(rule, SKIP, "-",
                                  "no entity in the extract carries this rule's tags"))
            continue
        for entity in targets:
            check = rule["check"]
            if check == "min_value":
                results.append(check_min(entity, rule))
            elif check == "max_value":
                results.append(check_max(entity, rule))
            elif check == "max_value_by_zone":
                results.append(check_max_by_zone(entity, rule, rules_doc, zone))
            elif check == "max_value_by_kind":
                results.append(check_max_by_kind(entity, rule, rules_doc))
            else:
                results.append(Result(rule, SKIP, entity.get("name", "?"),
                                      "unknown check type '%s'" % check))
    return results


def report(results, project_name):
    order = {FAIL: 0, UNVERIFIED: 1, SKIP: 2, PASS: 3}
    tally = {s: sum(1 for r in results if r.status == s)
             for s in (PASS, FAIL, UNVERIFIED, SKIP)}

    print()
    print("Norm check - %s" % project_name)
    print("=" * 78)
    for r in sorted(results, key=lambda r: (order[r.status], r.rule["id"])):
        if r.status == SKIP:
            continue
        print("[%-10s] %s %s  (%s)" % (r.status, r.rule["norm"],
                                       r.rule["article"], r.rule["id"]))
        print("             subject : %s" % r.subject)
        print("             %s" % r.detail)
        if r.status == UNVERIFIED and r.measured is not None:
            print("             measured value is %.3f, but there is no trusted "
                  "limit to judge it against" % r.measured)
        if r.status == FAIL:
            print("             -> %s" % r.rule["message"])
        print()

    print("-" * 78)
    print("PASS %d   FAIL %d   UNVERIFIED %d   SKIP %d"
          % (tally[PASS], tally[FAIL], tally[UNVERIFIED], tally[SKIP]))

    if tally[FAIL]:
        print()
        print("VERDICT: NON-COMPLIANT - failures above must be resolved.")
    elif tally[UNVERIFIED]:
        print()
        print("VERDICT: INCONCLUSIVE - no failures, but thresholds above were never")
        print("transcribed from the official text. This is NOT a pass. Transcribe the")
        print("cited articles into tools/norms/rules.json, then re-run.")
    elif tally[PASS] == 0:
        print()
        print("VERDICT: INCONCLUSIVE - nothing was actually evaluated.")
    else:
        print()
        print("VERDICT: COMPLIANT for the rules evaluated above.")
        print("Rules marked SKIP were not evaluated and carry no verdict.")
    return tally


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("extract", help="model extract JSON (see docs/commands.md)")
    ap.add_argument("--site", help="project site.json with thermal zone and PRC limits")
    ap.add_argument("--rules", default=str(RULES_PATH))
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    extract_path = Path(args.extract)
    if not extract_path.exists():
        print("error: extract not found: %s" % extract_path, file=sys.stderr)
        return 2
    with open(extract_path, encoding="utf-8") as fh:
        extract = json.load(fh)

    site = None
    if args.site:
        with open(args.site, encoding="utf-8") as fh:
            site = json.load(fh)

    rules_doc = load_rules(args.rules)
    apply_site_thresholds(rules_doc, site)
    results = run(extract, rules_doc, site)

    if args.as_json:
        print(json.dumps({
            "project": extract.get("project", extract_path.stem),
            "results": [r.as_dict() for r in results],
        }, indent=2, ensure_ascii=False))
        return 1 if any(r.status in (FAIL, UNVERIFIED) for r in results) else 0

    tally = report(results, extract.get("project", extract_path.stem))
    return 1 if (tally[FAIL] or tally[UNVERIFIED]) else 0


if __name__ == "__main__":
    sys.exit(main())
