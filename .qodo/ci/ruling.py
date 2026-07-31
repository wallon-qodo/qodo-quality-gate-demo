#!/usr/bin/env python3
"""Ruling tests: pin expected findings per rule, fail on drift.

Modelled on SonarQube's ruling suite. "52/57 recall" is not a useful CI signal --
five of those misses are documented structural limits of the pattern language and
will never be fixed. What matters is DRIFT: did today's behaviour change from the
reviewed baseline?

Three drift classes, all failures:
  REGRESSION      a fixture that used to fire no longer does
  NEW FALSE POS   a safe fixture that was clean now fires
  GAP CLOSED      a known-gap fixture now fires -- the rule got better, so the
                  baseline is stale. Not a bug, but it must not pass silently or
                  the baseline stops meaning anything.

  ruling.py <rules-dir> <fixtures-dir> --baseline b.json [--update]
"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

OPENGREP = "/Users/wallonwalusayi/.local/bin/opengrep"
BUCKETS = ("vulnerable", "safe", "evasion")


def _files(d):
    return sorted(f.name for f in d.iterdir()
                  if f.is_file() and not f.name.startswith(".")) if d.is_dir() else []


def observe(rules_dir, fixtures_dir):
    """One batched scan, attributed back to rule ids.

    Rules may live one-per-file or many-per-file, so records are keyed on the rule's
    declared `id`, never the filename. Fixtures live at <fixtures>/<rule id>/<bucket>/.
    A single opengrep invocation is ~2.3x faster than scanning per rule.
    """
    rules_dir, fixtures_dir = Path(rules_dir), Path(fixtures_dir)

    ids = []
    for f in sorted(rules_dir.glob("*.yml")) if rules_dir.is_dir() else [rules_dir]:
        doc = yaml.safe_load(f.read_text()) or {}
        ids.extend(r["id"] for r in doc.get("rules", []) if "id" in r)

    proc = subprocess.run([OPENGREP, "scan", "--config", str(rules_dir), "--json",
                           "--quiet", str(fixtures_dir)], capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {i: {"error": [f"opengrep produced no JSON: {proc.stderr.strip()[:200]}"]}
                for i in ids}

    # opengrep namespaces check_id by the config path, so match on suffix
    fired = {}
    for res in data.get("results", []):
        cid = res["check_id"]
        rid = next((i for i in ids if cid == i or cid.endswith("." + i)), cid)
        path = Path(res["path"])
        bucket = next((b for b in BUCKETS if f"/{b}/" in str(path)), "other")
        fired.setdefault(rid, {}).setdefault(bucket, set()).add(path.name)

    errs = [json.dumps(e)[:160] for e in data.get("errors", [])]
    out = {}
    for rid in ids:
        fx = fixtures_dir / rid
        if not fx.is_dir():
            out[rid] = {"error": [f"no fixture directory: {fx}"]}
            continue
        rec = {"errors": errs}
        for b in BUCKETS:
            rec[b] = {"files": _files(fx / b),
                      "fired": sorted(fired.get(rid, {}).get(b, set()))}
        out[rid] = rec
    return out


def diff(base, now):
    """Return (failures, notes). Failures fail the build."""
    fails, notes = [], []
    for rule in sorted(set(base) | set(now)):
        b, n = base.get(rule), now.get(rule)
        if b is None:
            fails.append((rule, "NEW RULE", "not in baseline -- run with --update after review"))
            continue
        if n is None:
            fails.append((rule, "RULE GONE", "in baseline but not found now"))
            continue
        if n.get("errors"):
            fails.append((rule, "ENGINE ERROR", "; ".join(n["errors"])[:200]))
        known = set(b.get("known_gaps", []))

        for bucket in BUCKETS:
            bb, nn = b.get(bucket) or {}, n.get(bucket) or {}
            was, is_ = set(bb.get("fired", [])), set(nn.get("fired", []))
            added_files = set(nn.get("files", [])) - set(bb.get("files", []))

            lost = was - is_
            if lost:
                fails.append((rule, "REGRESSION",
                              f"{bucket}: no longer fires on {sorted(lost)}"))
            gained = is_ - was
            for g in sorted(gained):
                if bucket == "safe":
                    fails.append((rule, "NEW FALSE POSITIVE", f"safe/{g} now fires"))
                elif g in known:
                    fails.append((rule, "GAP CLOSED",
                                  f"{bucket}/{g} was a known gap and now fires -- "
                                  "rule improved, refresh the baseline with --update"))
                elif g in added_files:
                    notes.append((rule, f"new fixture {bucket}/{g} fires (expected for a new TP)"))
                else:
                    fails.append((rule, "UNEXPECTED HIT", f"{bucket}/{g} newly fires"))
            for f in sorted(added_files - is_):
                if bucket == "vulnerable":
                    notes.append((rule, f"new fixture vulnerable/{f} does NOT fire -- "
                                        "add to known_gaps if intentional"))
    return fails, notes


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2 or "--baseline" not in sys.argv:
        sys.exit(__doc__)
    baseline_path = Path(sys.argv[sys.argv.index("--baseline") + 1])
    update = "--update" in sys.argv

    now = observe(args[0], args[1])

    if update or not baseline_path.exists():
        prior = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
        for rule, rec in now.items():
            gaps = prior.get(rule, {}).get("known_gaps")
            if gaps is None:
                v = rec.get("vulnerable") or {}
                gaps = sorted(set(v.get("files", [])) - set(v.get("fired", [])))
            rec["known_gaps"] = gaps
        baseline_path.write_text(json.dumps(now, indent=2, sort_keys=True))
        tot_gaps = sum(len(r.get("known_gaps", [])) for r in now.values())
        print(f"baseline written: {len(now)} rules, {tot_gaps} known gaps recorded")
        print("REVIEW IT before committing -- every known gap is a documented "
              "non-detection you are choosing to accept.")
        return 0

    base = json.loads(baseline_path.read_text())
    fails, notes = diff(base, now)

    tp = sum(len((r.get("vulnerable") or {}).get("fired", [])) for r in now.values())
    tv = sum(len((r.get("vulnerable") or {}).get("files", [])) for r in now.values())
    fp = sum(len((r.get("safe") or {}).get("fired", [])) for r in now.values())
    ts = sum(len((r.get("safe") or {}).get("files", [])) for r in now.values())
    gaps = sum(len(r.get("known_gaps", [])) for r in base.values())
    print(f"ruling: {len(now)} rules | vulnerable {tp}/{tv} | safe FP {fp}/{ts} | "
          f"known gaps {gaps}\n")

    for rule, msg in notes:
        print(f"  note  {rule}: {msg}")
    if notes:
        print()
    if fails:
        for rule, kind, msg in fails:
            print(f"  [{kind}] {rule}\n         {msg}")
        print(f"\nFAIL - {len(fails)} drift(s) from baseline")
        return 1
    print("PASS - no drift from baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
