#!/usr/bin/env python3
"""Migrate B-mode rules to frozen schema v1.

Written after doing it by hand and getting it wrong twice:
  - regex surgery on nested YAML orphaned a key's children and broke the file
  - the frozen block re-declared keys that already existed further down, producing
    duplicate keys that pyyaml tolerates (last-wins) but opengrep rejects outright

So this script: never regexes structured YAML, never blindly inserts a key that may
already exist, PRESERVES limitations rather than regenerating it, and re-parses with
duplicate detection after every write. A rule that fails post-write is rolled back.

  migrate_to_v1.py <rules-dir> --map primaries.json [--apply]
"""
import json
import re
import shutil
import sys
from pathlib import Path

import yaml

# citation keys that held locally-invented ints or corpus strings; their content is
# preserved under satisfies_uncited, never silently dropped
LEGACY_CITATION_KEYS = [
    "qodo_rule_id", "qodo_primary_rule_id", "qodo_rule_ids", "qodo_rule_ids_all",
    "qodo_rule_id_map", "satisfies", "citation_count", "tier",
    "qodo_rule_ids_partial", "qodo_rule_ids_out_of_language", "qodo_rule_ids_rejected",
    "qodo_rule_ids_descoped", "qodo_rule_ids_cluster_other_languages", "partial_citations",
]
FROZEN_ORDER = ["qodo_schema_version", "qodo_integration_mode", "qodo_finding_source",
                "qodo_action_level", "qodo_primary_rule_id", "qodo_rule_ids",
                "version", "portability_tier", "confidence", "limitations"]
TIER_MAP = {"A": "A", "B": "B", "AB": "AB"}


class DupLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    out, dups = {}, []
    for k_node, v_node in node.value:
        k = loader.construct_object(k_node, deep=deep)
        if k in out:
            dups.append(k)
        out[k] = loader.construct_object(v_node, deep=deep)
    if dups:
        loader.dups.extend(dups)
    return out


DupLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def parse_strict(text):
    ldr = DupLoader(text)
    ldr.dups = []
    try:
        doc = ldr.get_single_data()
    finally:
        dups = list(ldr.dups)
        ldr.dispose()
    return doc, dups


def normalise_tier(v):
    """'A + B (intrafile taint...)' -> ('AB', 'intrafile taint...'). Prose is kept."""
    if not isinstance(v, str):
        return "A", None
    s = v.strip()
    if s in TIER_MAP:
        return TIER_MAP[s], None
    has_a, has_b = re.search(r"\bA\b", s), re.search(r"\bB\b", s)
    tier = "AB" if (has_a and has_b) else ("B" if has_b else "A")
    notes = s if s != tier else None
    return tier, notes


def collect_uncited(meta):
    """Every corpus assertion referenced by a legacy key, as corpus:id strings."""
    found = set()
    for k in LEGACY_CITATION_KEYS:
        v = meta.get(k)
        if isinstance(v, list):
            found |= {x for x in v if isinstance(x, str) and ":" in x}
        elif isinstance(v, dict):
            for kk, vv in v.items():
                if isinstance(vv, str) and ":" in vv:
                    found.add(vv)
                elif isinstance(vv, list):
                    found |= {f"{kk}:{i}" for i in vv if isinstance(i, str)}
    return sorted(found)


def migrate(path, primary_id, apply=False):
    original = path.read_text()
    doc, dups = parse_strict(original)
    if dups:
        return False, f"refusing to migrate: pre-existing duplicate keys {sorted(set(dups))}"
    rule = doc["rules"][0]
    meta = rule.get("metadata") or {}

    limitations = (meta.get("limitations") or "").strip()
    if len(limitations) < 30:
        return False, "limitations missing or trivial; write it before migrating"

    tier, notes = normalise_tier(meta.get("portability_tier"))
    uncited = collect_uncited(meta)
    prior_uncited = meta.get("satisfies_uncited")

    new = {k: v for k, v in meta.items()
           if k not in LEGACY_CITATION_KEYS and k not in FROZEN_ORDER
           and k not in ("satisfies_uncited", "tier_notes")}
    frozen = {
        "qodo_schema_version": 1,
        "qodo_integration_mode": "findings_adapter",
        "qodo_finding_source": "StaticAnalysisFinding",
        "qodo_action_level": meta.get("qodo_action_level", "action_required"),
        "qodo_primary_rule_id": primary_id,
        "qodo_rule_ids": [primary_id],
        "version": meta.get("version", "1.0.0"),
        "portability_tier": tier,
        "confidence": meta.get("confidence", "HIGH"),
        "limitations": limitations,      # PRESERVED, never regenerated
    }
    if notes:
        frozen["tier_notes"] = notes
    if uncited or prior_uncited:
        merged = sorted(set(uncited) | set(prior_uncited or []))
        frozen["satisfies_uncited"] = merged
        frozen["satisfies_uncited_note"] = (
            f"{len(merged)} corpus controls this matcher satisfies. NOT citations: none has a "
            "platform ruleId yet, and findings_rule_engine matches int ids only, so citing "
            "them would claim attribution the gate cannot make. Load each via "
            "POST /rules/v1/rule, then promote its id into qodo_rule_ids."
        )
    rule["metadata"] = {**frozen, **new}

    out = yaml.safe_dump(doc, sort_keys=False, width=100, allow_unicode=True, default_flow_style=False)
    check, check_dups = parse_strict(out)
    if check_dups:
        return False, f"post-write duplicate keys {sorted(set(check_dups))} - not written"
    cm = check["rules"][0]["metadata"]
    if cm.get("limitations", "").strip() != limitations:
        return False, "limitations not preserved byte-for-byte - not written"

    if apply:
        shutil.copyfile(path, path.with_suffix(".yml.pre-v1"))
        path.write_text(out)
    return True, (f"tier={tier}{' (+notes)' if notes else ''} "
                  f"primary={primary_id} uncited={len(uncited)} lim={len(limitations)}c")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    mp = sys.argv[sys.argv.index("--map") + 1] if "--map" in sys.argv else None
    if not args or not mp:
        sys.exit(__doc__)
    ids = json.loads(Path(mp).read_text())

    print("APPLY" if apply else "DRY RUN (no writes)")
    ok = fail = 0
    for f in sorted(Path(args[0]).glob("*.yml")):
        if f.stem not in ids:
            print(f"  skip   {f.stem:<26} (no primary ruleId in map)")
            continue
        good, msg = migrate(f, ids[f.stem], apply)
        print(f"  {'OK  ' if good else 'FAIL'}   {f.stem:<26} {msg}")
        ok, fail = (ok + 1, fail) if good else (ok, fail + 1)
    print(f"\n{ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
