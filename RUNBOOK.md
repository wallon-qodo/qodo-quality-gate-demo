# Runbook

## 1. Qodo side

Add this repo to your Qodo workspace (Qodo app installed on the repo).

Then set the merge gate. `merge_automation` is **platform-managed** -- it is NOT
read from `.pr_agent.toml`:

```bash
curl -X PATCH https://api.qodo.ai/config/v1/repo-settings \
  -H "Authorization: Bearer $QODO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "wallon-qodo/qodo-opengrep-gate-demo",
    "merge_automation": {
      "enabled": true,
      "default": "approve",
      "rules": [
        {
          "when": { "category": "Security", "action_level": ">=action_required", "at_least": 1 },
          "decision": "block"
        }
      ]
    }
  }'
```

`default: "approve"` means a clean PR gets a bot APPROVE, which satisfies the
required-approval branch protection rule and goes green.

Verify it persisted:
```bash
curl -s https://api.qodo.ai/config/v1/values -H "Authorization: Bearer $QODO_TOKEN" | jq .config.merge_automation
```

## 2. Branch protection

Settings -> Branches -> `main` -> Edit. Two separate settings, one per gate:

| Gate | Setting | Value |
|---|---|---|
| Opengrep | Require status checks to pass | add `Deterministic Quality Gate (Opengrep)` |
| Qodo | Require a pull request before merging -> Require approvals | `1` |

Also enable **Restrict who can dismiss pull request reviews** -- otherwise a dev
dismisses Qodo's REQUEST_CHANGES and self-clears the gate.

The Opengrep check will not appear in the search box until it has reported once.
Open PR 1 first, then add it.

## 3. Open the demo PRs

```bash
scripts/make-prs.sh          # dry run, prints what it will do
scripts/make-prs.sh --apply  # creates the three branches and PRs
```

## 4. Expected result

| PR | Opengrep check | Qodo review | Merge button |
|---|---|---|---|
| 1 weak-hash | red (SEC-CRYPTO-01) | CHANGES_REQUESTED | blocked |
| 2 missing-authz | **green** | CHANGES_REQUESTED | blocked |
| 3 clean-refactor | green | APPROVED | enabled |

## Gotchas

- Qodo re-reviews on push are **incremental** and do not auto-clear prior
  findings on the same PR. To demo fix-then-unblock, open a fresh PR.
- Canonical review command is `/agentic_review` (`/review` is legacy).
- `--json` exits 0 even with findings. The gate uses `--error` for exactly this
  reason.
- Do not add `paths:` filters to the workflow. A required check that skips is
  treated as pending, not passing, and nothing merges.
