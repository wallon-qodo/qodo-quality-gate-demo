#!/usr/bin/env python3
"""Phase 0 gate: schema conformance + ruleId integrity for Qodo Quality Gate rules.

This is the mechanism the 8501 collision needed. Fixing the six rules by hand was
a one-off; this stops it recurring.

Checks, in order of how badly they bite:
  E1  qodo_primary_rule_id collides across matchers        <- the original bug
      (E1-E4 apply only to qodo_integration_mode: findings_adapter -- in status_check
       mode the CI exit code is the gate and citations are not read)
  E2  an id is in the legacy locally-invented 8000-8999 band
  E3  qodo_primary_rule_id not a member of qodo_rule_ids
  E4  a cited id does not resolve on the platform (needs --online)
  E5  any JSON Schema violation -- required keys, enums, semver, limitations minLength,
      and the anyOf "must have a pattern block or mode:taint" rule. The schema at
      schema/qodo-opengrep-rule.schema.json is the SINGLE source of truth; this script
      no longer reimplements those checks (that drift is what let portability_tier and
      confidence enums go unenforced).
  E9  duplicate keys -- pyyaml last-wins silently, opengrep rejects the file outright

Exit 1 on any error. Warnings do not fail the build.

  validate_rules.py <rules-dir> [--online]
"""
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.exit("jsonschema required: pip install jsonschema")

try:
    import yaml
except ImportError:
    sys.exit("pyyaml required")

class _DupDetectingLoader(yaml.SafeLoader):
    """SafeLoader that records duplicate mapping keys instead of silently last-winning."""


def _construct_mapping(loader, node, deep=False):
    mapping, dups = {}, []
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            dups.append(key)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    if dups:
        loader.duplicate_keys.extend(dups)
    return mapping


_DupDetectingLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml_strict(path):
    """Return (doc, duplicate_keys). Mirrors what opengrep will accept."""
    loader = _DupDetectingLoader(path.read_text())
    loader.duplicate_keys = []
    try:
        doc = loader.get_single_data()
    finally:
        dups = list(loader.duplicate_keys)
        loader.dispose()
    return doc, dups


SCHEMA_VERSION = 1
LEGACY_BAND = range(8000, 9000)   # the invented space that caused the collision
SEV_TO_LEVEL = {"ERROR": "action_required", "WARNING": "remediation_recommended",
                "INFO": "informational"}
PLATFORM = os.environ.get("QODO_PLATFORM_URL", "https://qodo-platform.qodo.ai")
SCHEMA_PATH = Path(__file__).parent / "schema" / "qodo-opengrep-rule.schema.json"


def load_schema():
    if not SCHEMA_PATH.exists():
        sys.exit(f"schema not found: {SCHEMA_PATH}")
    return json.loads(SCHEMA_PATH.read_text())


def schema_errors(rule, schema):
    """Every structural/enum violation, straight from the schema. No reimplementation."""
    validator = jsonschema.Draft202012Validator(schema)
    out = []
    for e in sorted(validator.iter_errors(rule), key=lambda x: list(x.absolute_path)):
        loc = ".".join(str(x) for x in e.absolute_path) or "<root>"
        out.append(f"{loc}: {e.message}")
    return out


def token():
    if os.environ.get("QODO_API_KEY"):
        return os.environ["QODO_API_KEY"]
    for path, key in ((Path.home() / ".qodo/config.json", "API_KEY"),
                      (Path.home() / ".qodo/skill_auth.json", "id_token")):
        try:
            v = json.loads(path.read_text()).get(key)
            if v:
                return v
        except Exception:
            continue
    return None


_resolved = {}


def resolves(rule_id, tok):
    """True if the id is a real platform rule. Cached; None if unknown (network/auth)."""
    if rule_id in _resolved:
        return _resolved[rule_id]
    req = urllib.request.Request(f"{PLATFORM}/rules/v1/rule/{rule_id}",
                                headers={"Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            ok = r.status == 200 and bool(json.load(r).get("name"))
    except urllib.error.HTTPError as e:
        ok = False if e.code in (403, 404) else None
    except Exception:
        ok = None
    _resolved[rule_id] = ok
    return ok


def load(rules_dir):
    out = []
    for f in sorted(Path(rules_dir).rglob("*.yml")):
        try:
            doc, dups = load_yaml_strict(f)
        except Exception as e:
            out.append((f, None, f"unparseable YAML: {e}"))
            continue
        if dups:
            # opengrep raises InvalidRuleSchemaError and refuses to load the file
            out.append((f, None, "E9 duplicate keys (opengrep will reject this file): "
                                 + ", ".join(sorted(set(map(str, dups))))))
            continue
        for r in (doc or {}).get("rules", []):
            out.append((f, r, None))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    online = "--online" in sys.argv
    if not args:
        sys.exit(__doc__)
    rules_dir = args[0]

    errors, warnings = [], []
    primaries = {}          # primary id -> [rule ids using it]
    tok = token() if online else None
    if online and not tok:
        warnings.append("--online requested but no token found; E4 skipped")
        online = False

    entries = load(rules_dir)
    if not entries:
        sys.exit(f"no rules found under {rules_dir}")

    schema = load_schema()

    for f, r, parse_err in entries:
        if parse_err:
            errors.append(("E0", f.name, parse_err))
            continue
        rid = r.get("id", "<no id>")
        where = f"{f.name}:{rid}"
        m = r.get("metadata") or {}

        # E5 -- everything the schema can express: required keys, enums, patterns,
        # semver, minLength on limitations, the anyOf pattern-block requirement.
        for msg in schema_errors(r, schema):
            errors.append(("E5", where, msg))

        # --- checks JSON Schema structurally cannot express ---

        b_mode = m.get("qodo_integration_mode") == "findings_adapter"
        ids = [i for i in (m.get("qodo_rule_ids") or []) if isinstance(i, int)]
        prim = m.get("qodo_primary_rule_id")

        # E2 -- the legacy invented band
        legacy = sorted({i for i in ids if i in LEGACY_BAND} |
                        ({prim} if isinstance(prim, int) and prim in LEGACY_BAND else set()))
        if legacy:
            errors.append(("E2", where,
                           f"ids in the legacy 8000-8999 invented band: {legacy[:8]}. "
                           "Citations must be real platform ruleIds from POST /rules/v1/rule."))

        # E3 -- primary must be among the citations (cross-field)
        if isinstance(prim, int) and ids and prim not in ids:
            errors.append(("E3", where, f"qodo_primary_rule_id {prim} not in qodo_rule_ids"))
        if isinstance(prim, int) and b_mode:
            primaries.setdefault(prim, []).append(where)

        # severity <-> action_level coherence: a convention, so warn not fail
        sev = r.get("severity")
        if sev in SEV_TO_LEVEL and m.get("qodo_action_level") not in (None, SEV_TO_LEVEL[sev]):
            warnings.append((where, f"severity {sev} conventionally maps to "
                                    f"{SEV_TO_LEVEL[sev]}, got {m.get('qodo_action_level')}"))

        # E4 -- do the cited ids actually exist on the platform
        if online and b_mode:
            for i in dict.fromkeys(ids):
                got = resolves(i, tok)
                if got is False:
                    errors.append(("E4", where, f"rule id {i} does not resolve on the platform"))
                elif got is None:
                    warnings.append((where, f"could not verify rule id {i} (network/auth)"))

    # E1 -- the original bug
    for pid, users in sorted(primaries.items()):
        if len(users) > 1:
            errors.append(("E1", ", ".join(users),
                           f"qodo_primary_rule_id {pid} claimed by {len(users)} matchers"))

    n = sum(1 for _, r, e in entries if r and not e)
    print(f"validated {n} rules from {rules_dir}"
          f"{' (online id checks ON)' if online else ' (offline: E4 skipped)'}\n")
    if warnings:
        print(f"warnings ({len(warnings)}):")
        for w in warnings:
            print("  ~", w if isinstance(w, str) else f"{w[0]}: {w[1]}")
        print()
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for code, where, msg in errors:
            print(f"  [{code}] {where}\n         {msg}")
        print(f"\nFAIL - {len(errors)} error(s)")
        return 1
    print("PASS - schema conformant, ids unique, no legacy id band, no duplicate keys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
