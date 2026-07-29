# Qodo + Opengrep Quality Gate Demo

Two independent gates on one PR. Both must pass before a merge is possible.

| Gate | Mechanism | Catches | Determinism |
|---|---|---|---|
| **Opengrep** | CI required **status check** | syntactic floor: banned APIs, dangerous literals, unsafe shapes | same commit -> identical findings, every run |
| **Qodo** | **REQUEST_CHANGES review** vote | judgment: authorization, business logic, exploitability | LLM reasoning, non-reproducible by design |

Branch protection ANDs them. They are different provider primitives -- a status
check and a review vote -- so they compose without interfering.

## The point of this demo

The two gates are **complementary, not redundant**. Verified live on this repo:

| PR | Defect | Opengrep | Qodo | Merge | Blocked by |
|---|---|---|---|---|---|
| [#1](../../pull/1) | `hashlib.md5()` for password storage | **FAILURE** | APPROVED | **BLOCKED** | the status check |
| [#4](../../pull/4) | ownership check removed from `get_invoice` | **SUCCESS** | **CHANGES_REQUESTED** | **BLOCKED** | the review vote |
| [#3](../../pull/3) | harmless refactor | SUCCESS | APPROVED | **CLEAN** | — mergeable — |

Each PR is blocked by a *different* gate, and the clean one passes both. That is
the whole architecture in three rows.

**#4 is the one that matters.** Opengrep passes it with zero findings and is
*correct* to: there is no banned API and no dangerous literal, only an absent
authorization check. A pattern matcher cannot express "this function was supposed
to verify ownership." Qodo caught it — and caught more than was planted:

> **Invoice ownership bypass** `Bug` `Security` — *Action required*
> "Removing the account comparison makes `get_invoice` return another account's
> invoice to any caller who supplies its ID. Because `refund` relies on this
> lookup before calling `write_refund`, the same bypass also permits
> cross-account refunds."

**#1 is the inverse.** Opengrep decides it mechanically and identically on every
run — the property an auditor wants as evidence. Note Qodo *approved* #1: there
is no platform rule for weak hashing scoped to this repo, so `rule_compliance`
found no match and fell through to `default: approve`. The deterministic gate
carries that case alone, with no platform rule required. That asymmetry is the
argument for running both.

## How each gate actually blocks

Two different provider primitives, which is why they compose:

| Gate | Primitive | Wired via |
|---|---|---|
| Opengrep | required **status check** | `--error` → non-zero exit → check fails → branch protection |
| Qodo | **REQUEST_CHANGES review** | `merge_automation` → `rule_compliance` matches a platform rule id → review vote → branch protection |

Qodo's half needs a **platform rule with a stable int id**. LLM-derived findings
arrive with no rule id and are not matchable by `rule_compliance` — they post as
advisory comments and do not block. This repo is gated by rule **2397096**
("Authorization checks must not be removed from record accessors"), scoped to
`/wallon-qodo/qodo-opengrep-gate-demo/` so it fires only here.

## Layout

```
.github/workflows/quality-gate.yml   Opengrep CI job (--error -> non-zero exit -> check fails)
.qodo/opengrep/security.yml          7 deterministic rules
.pr_agent.toml                       Qodo review config
app/                                 clean baseline
```

## Rules

7 rules, ported from a set measured against 288 real production files
(0 false positives) before landing here.

| Rule | CWE | Frameworks satisfied |
|---|---|---|
| SEC-CRYPTO-01 weak hash | CWE-327, CWE-1240 | FIPS-HR-01, PCI-DSS 6.2.4, NIST SC-13 |
| SEC-SECRET-01 hard-coded secret | CWE-798, CWE-259 | FIPS-HR-06, PCI-DSS 6.2.4, HIPAA-HR-04 |
| SEC-SQLI-01 SQL concatenation | CWE-89 | PCI-DSS 6.2.4, OWASP-HR-03 |
| SEC-DESER-01 unsafe deserialization | CWE-502 | OWASP-HR-06, STIG-HR-06 |
| SEC-CMDI-01 OS command injection | CWE-78 | OWASP-HR-03, STIG-HR-06 |
| SEC-TLS-01 TLS verification disabled | CWE-295 | FIPS-HR-04, PCI-DSS 4.2.1 |
| SEC-RANDOM-01 weak PRNG | CWE-338, CWE-330 | FIPS-HR-02 |

Each rule carries `metadata.qodo_rule_id`. Architecture A (this demo) does not
read it -- it is there so the same ruleset can later feed Qodo's findings model
directly instead of running as a separate status check.

## Setup

See [RUNBOOK.md](RUNBOOK.md).
