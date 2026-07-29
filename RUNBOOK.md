# Runbook

## 1. Code Review side

Add this repo to your Qodo workspace, then wire the merge gate.

`merge_automation` blocks via `rule_compliance` on **stable integer rule ids**. A
finding the LLM derives on its own has no rule id and cannot be gated. So the
authorization defect in PR 2 needs a platform rule scoped to this repo.

```bash
# a) create the rule (schema: content / good_examples / bad_examples;
#    severity is error|warning|recommendation -- NOT "critical")
~/.claude/skills/bulk-rules/scripts/bulk-add-rules.sh \
  --file .qodo/rules/authorization.json \
  --scope "/wallon-qodo/qodo-quality-gate-demo/" --verify

# b) find its ruleId (the list endpoint is paginated, 50/page)
SC=$(python3 -c "import urllib.parse;print(urllib.parse.quote('/wallon-qodo/qodo-quality-gate-demo/',safe=''))")
curl -s "https://qodo-platform.qodo.ai/rules/v1/rules?scopes=$SC&state=active&page=1" \
  -H "Authorization: Bearer $QODO_TOKEN" | jq '.[] | {ruleId, name}'

# c) append that id to merge_automation's rule_compliance clause.
#    READ the current config first and append -- do not overwrite, or you will
#    drop the ids other repos depend on.
curl -s https://qodo-platform.qodo.ai/config/v1/values \
  -H "Authorization: Bearer $QODO_TOKEN" | jq .config.merge_automation

curl -X PATCH https://qodo-platform.qodo.ai/config/v1/settings \
  -H "Authorization: Bearer $QODO_TOKEN" -H "Content-Type: application/json" \
  -d '{"values":[{"key":"merge_automation","value": <the object, with your id appended> }]}'
```

`default: "approve"` is what lets PR 3 go green via bot approval, which satisfies
the required-approval branch protection rule.

## 2. Branch protection

Settings -> Branches -> `main` -> Edit. One setting per surface:

| Surface | Setting | Value |
|---|---|---|
| Quality Gate | Require status checks to pass | add `Qodo Quality Gate` |
| Code Review | Require a pull request before merging -> Require approvals | `1` |

Also enable **Restrict who can dismiss pull request reviews**, or a dev can
dismiss the CHANGES_REQUESTED and self-clear the gate.

The check will not appear in the search box until it has reported once. Open the
PRs first, then add it.

Note `enforce_admins` is off in this demo, so an admin can still push straight to
`main`. Turn it on for a realistic customer configuration.

## 3. Open the demo PRs

```bash
scripts/make-prs.sh          # dry run
scripts/make-prs.sh --apply
```

## 4. Expected result

| PR | Quality Gate | Code Review | Merge |
|---|---|---|---|
| 1 weak-hash | red | approves (no rule id for weak hashing) | blocked |
| 2 missing-authz | **green** | CHANGES_REQUESTED | blocked |
| 3 clean-refactor | green | APPROVED | enabled |

## Gotchas

- Code Review re-reviews on push are **incremental** and do not clear prior
  findings on the same PR. To demo fix-then-unblock, open a fresh PR.
- Canonical review command is `/agentic_review` (`/review` is legacy).
- If auto-review is off, comment `/agentic_review` to trigger it.
- `--json` exits 0 even with findings. The gate uses `--error` for that reason.
- Do not add `paths:` filters to the workflow. A required check that skips counts
  as pending, not passing, and nothing merges.
