#!/usr/bin/env bash
# Push the three demo branches and open their PRs.
#   make-prs.sh           dry run
#   make-prs.sh --apply   actually push + open
set -euo pipefail
APPLY="${1:-}"

run() {
  if [ "$APPLY" = "--apply" ]; then echo "+ $*"; "$@"; else echo "  would run: $*"; fi
}

open_pr() {
  local branch="$1" title="$2" body="$3"
  run git push -u origin "$branch" --force-with-lease
  if [ "$APPLY" = "--apply" ]; then
    gh pr create --base main --head "$branch" --title "$title" --body "$body" || \
      echo "  (PR for $branch may already exist)"
  else
    echo "  would run: gh pr create --head $branch --title '$title'"
  fi
}

open_pr defect/weak-hash \
  "perf: speed up password hashing" \
  "Swaps the PBKDF2 derivation for a single-pass digest to cut login latency.

**Expected result:** Qodo Quality Gate FAILS (SEC-CRYPTO-01, CWE-327). Qodo also flags it.
Merge blocked by the required status check."

open_pr defect/missing-authz \
  "refactor: simplify invoice lookup" \
  "Drops a redundant branch in \`get_invoice\`.

**Expected result:** Qodo Quality Gate PASSES -- there is no banned API or dangerous
literal here, only an absent ownership check, which a pattern matcher cannot
express. Qodo Code Review casts REQUEST_CHANGES. Merge blocked by the review vote alone.

This is the PR that proves the two gates are complementary."

open_pr chore/clean-refactor \
  "chore: extract account query to a module constant" \
  "No behaviour change; the query stays parameterised.

**Expected result:** both gates green, merge enabled."

echo
if [ "$APPLY" != "--apply" ]; then echo "dry run complete -- re-run with --apply"; fi
