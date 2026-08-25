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

## 5. Plain-English headlines inside the findings comment

Qodo leads each finding with the engine's technical title. Right for the author of
the diff, wrong for a reviewer scanning sixteen of them. `headline_rewrite.py`
rewrites that lead line as an outcome headline and adds a consequence-first block
under it, in place, inside Qodo's own comment.

```bash
# 1. Parse only -- no model, no API. Run this first on an unfamiliar comment.
gh api repos/OWNER/REPO/issues/comments/COMMENT_ID --jq .body > body.md
python3 .qodo/ci/headline_rewrite.py --body-file body.md --dry-run

# 2. Translate and preview the rewritten body, still without touching the PR.
python3 .qodo/ci/headline_rewrite.py --body-file body.md --out rewritten.md

# 3. Apply to the live PR, then hold it against Qodo's re-reviews.
python3 .qodo/ci/headline_rewrite.py --repo OWNER/REPO --pr N \
  --wait 300 --watch 600 --stable 180
```

Wording comes from the `plain-english-findings` engine, imported from
`--engine-dir` (default `~/.claude/skills/plain-english-findings`), never copied --
the report and the PR comment share one copy of the prompt contract or they drift.

### Gotchas

- **There is no product-supported injection point.** This edits Qodo's posted
  comment through the GitHub API. `GITHUB_TOKEN` can edit another GitHub App's
  comment (verified); Bitbucket Server cannot do this at all.
- **Qodo rewrites its comment on every re-review**, which reverts the headlines.
  The watch loop re-applies until the rewrite survives `--stable` seconds. A
  re-review after `--watch` expires reverts them until the next push.
- **Never run the local loop while CI is running one.** Last writer wins.
- Re-running is free and idempotent: headlines are cached by a content hash of the
  finding, and a body that already carries the blocks is returned unchanged.
- A finding the model does not return a headline for is left exactly as Qodo wrote
  it. An unreachable model is a no-op, not a failure.
