#!/usr/bin/env python3
"""Plan export verification + 3D render gate.

Enforces the repo's verification rule: after a geometry change, an export must
actually exist, be newer than the model that produced it, and be non-trivial.
A plan that opens without error can still be empty, blank, or stale - this
catches those three cases mechanically.

What it CANNOT do is tell you the plan is architecturally right. It reports
"an export exists and is current", never "the design is correct". After a green
run you still have to open the file and look at it.

Usage (one version folder at a time):
    python tools/render_check.py projects/<Name>/versions/<vN>
    python tools/render_check.py projects/<Name>/versions/<vN> --require dxf,pdf
    python tools/render_check.py projects/<Name>/versions/<vN> --json

The model (.FCStd / .blend) lives in exports/model/; it is the reference the other
exports are compared against, not an export itself. plans/ and model/ are still
searched for projects that predate that layout.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# An export smaller than this is almost certainly a blank sheet.
MIN_BYTES = {
    ".dxf": 2048,
    ".pdf": 4096,
    ".png": 8192,
    ".jpg": 8192,
    ".ifc": 2048,
    ".svg": 1024,
}
DEFAULT_MIN = 1024

MODEL_SUFFIXES = (".FCStd", ".blend")
OK, STALE, THIN, MISSING = "OK", "STALE", "THIN", "MISSING"


def newest(paths):
    best = None
    for p in paths:
        if best is None or p.stat().st_mtime > best.stat().st_mtime:
            best = p
    return best


def collect_models(project):
    models = []
    for sub in ("exports/model", "plans", "model"):
        d = project / sub
        if d.is_dir():
            for suffix in MODEL_SUFFIXES:
                models += [p for p in d.rglob("*" + suffix)
                           if not p.name.startswith("~")]
    return models


def collect_exports(project):
    d = project / "exports"
    if not d.is_dir():
        return []
    return [p for p in d.rglob("*") if p.is_file() and not p.name.startswith(".")
            and p.suffix not in MODEL_SUFFIXES]


def check(project, required):
    models = collect_models(project)
    exports = collect_exports(project)
    newest_model = newest(models)

    findings = []
    by_ext = {}
    for e in exports:
        by_ext.setdefault(e.suffix.lower(), []).append(e)

    for ext in required:
        ext = ext if ext.startswith(".") else "." + ext
        group = by_ext.get(ext, [])
        if not group:
            findings.append({
                "export": ext, "status": MISSING, "path": None,
                "detail": "no %s export found under %s/exports/" % (ext, project.name),
            })
            continue

        latest = newest(group)
        size = latest.stat().st_size
        floor = MIN_BYTES.get(ext, DEFAULT_MIN)
        rel = latest.relative_to(project)

        if size < floor:
            findings.append({
                "export": ext, "status": THIN, "path": str(rel), "bytes": size,
                "detail": "%d bytes, below the %d-byte floor for %s - "
                          "likely an empty sheet" % (size, floor, ext),
            })
            continue

        if newest_model is not None:
            lag = latest.stat().st_mtime - newest_model.stat().st_mtime
            if lag < 0:
                findings.append({
                    "export": ext, "status": STALE, "path": str(rel),
                    "bytes": size,
                    "detail": "older than %s by %s - re-export before trusting it"
                              % (newest_model.name, human(-lag)),
                })
                continue

        findings.append({
            "export": ext, "status": OK, "path": str(rel), "bytes": size,
            "detail": "%d bytes, newer than the model" % size,
        })

    return findings, newest_model, exports


def human(seconds):
    seconds = int(seconds)
    if seconds < 90:
        return "%ds" % seconds
    if seconds < 5400:
        return "%dm" % (seconds // 60)
    if seconds < 172800:
        return "%dh" % (seconds // 3600)
    return "%dd" % (seconds // 86400)


def report(project, findings, newest_model, exports):
    print()
    print("Render check - %s" % project.name)
    print("=" * 78)
    if newest_model:
        age = human(time.time() - newest_model.stat().st_mtime)
        print("newest model : %s  (modified %s ago)"
              % (newest_model.relative_to(project), age))
    else:
        print("newest model : none found under exports/model/ (or legacy plans/, model/)")
    print("exports found: %d file(s)" % len(exports))
    print()

    for f in findings:
        print("[%-7s] %s" % (f["status"], f["export"]))
        if f.get("path"):
            print("           %s" % f["path"])
        print("           %s" % f["detail"])
        print()

    bad = [f for f in findings if f["status"] != OK]
    print("-" * 78)
    if bad:
        print("GATE: BLOCKED - %d of %d export(s) failed."
              % (len(bad), len(findings)))
        print("Fix the exports above, then re-run.")
    else:
        print("GATE: exports exist, are current, and are non-trivial.")
        print()
        print("This is NOT a design verdict. A render is not a measurement:")
        print("  1. Open the export and LOOK at it.")
        print("  2. Ask form-auditor for numbers off the 3D form.")
        print("  3. Ask norm-checker before claiming compliance.")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", help="path to projects/<Name>")
    ap.add_argument("--require", default="dxf,pdf",
                    help="comma-separated extensions that must be present "
                         "(default: dxf,pdf)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    project = Path(args.project)
    if not project.is_dir():
        print("error: not a directory: %s" % project, file=sys.stderr)
        return 2

    required = [r.strip() for r in args.require.split(",") if r.strip()]
    findings, newest_model, exports = check(project, required)

    if args.as_json:
        print(json.dumps({
            "project": project.name,
            "newest_model": str(newest_model) if newest_model else None,
            "findings": findings,
        }, indent=2, ensure_ascii=False))
        return 1 if any(f["status"] != OK for f in findings) else 0

    return report(project, findings, newest_model, exports)


if __name__ == "__main__":
    sys.exit(main())
