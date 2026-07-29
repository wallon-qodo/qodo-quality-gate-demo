# Qodo Quality Gate + Qodo Code Review

Two Qodo surfaces on one PR. Both must pass before a merge is possible.

| Surface | Mechanism | Catches | Determinism |
|---|---|---|---|
| **Qodo Quality Gate** | CI required **status check** | syntactic floor: banned APIs, dangerous literals, unsafe shapes | same commit -> identical findings, every run |
| **Qodo Code Review** | **REQUEST_CHANGES review** vote | judgment: authorization, business logic, exploitability | LLM reasoning, non-reproducible by design |

Branch protection ANDs them. They are different provider primitives -- a status
check and a review vote -- so they compose without interfering.

> The Quality Gate's analysis engine is **Opengrep** (LGPL-2.1), invoked as an
> unmodified external binary. "Qodo Quality Gate" names the policy layer: the rule
> set, severity mapping, CI wiring, and merge decision. See [NOTICE](NOTICE).

## The point of this demo

The two surfaces are **complementary, not redundant**. Three PRs:

| PR | Defect | Quality Gate | Code Review | Merge | Blocked by |
|---|---|---|---|---|---|
| 1 | `hashlib.md5()` for password storage | **FAIL** | approves | **BLOCKED** | the status check |
| 2 | ownership check removed from `get_invoice` | **PASS** | **CHANGES_REQUESTED** | **BLOCKED** | the review vote |
| 3 | harmless refactor | PASS | APPROVED | **CLEAN** | -- mergeable -- |

Each PR is blocked by a *different* surface, and the clean one passes both.

**PR 2 is the one that matters.** The Quality Gate passes it with zero findings and
is *correct* to: there is no banned API and no dangerous literal, only an absent
authorization check. A pattern matcher cannot express "this function was supposed
to verify ownership." Code Review catches it.

**PR 1 is the inverse.** The Quality Gate decides it mechanically and identically
on every run -- the property an auditor wants as evidence. Code Review may well
*approve* PR 1, because a hard block from Code Review requires a platform rule with
a stable integer id, and there is none for weak hashing scoped here. The
deterministic gate carries that case alone. That asymmetry is the argument for
running both.

## How each surface actually blocks

| Surface | Primitive | Wired via |
|---|---|---|
| Quality Gate | required **status check** | `--error` -> non-zero exit -> check fails -> branch protection |
| Code Review | **REQUEST_CHANGES review** | `merge_automation` -> `rule_compliance` matches a platform rule id -> review vote -> branch protection |

Code Review's half needs a **platform rule with a stable int id**. LLM-derived
findings arrive with no rule id, are not matchable by `rule_compliance`, and post
as advisory comments that do **not** block. This is the single most important
constraint to understand before promising that Code Review blocks on severity.

## Layout

```
.github/workflows/quality-gate.yml   status check (--error -> non-zero exit)
.qodo/quality-gate/security.yml      7 deterministic rules
.pr_agent.toml                       Code Review config
NOTICE                               third-party attribution (Opengrep, LGPL-2.1)
app/                                 clean baseline
```

## Rules

7 rules, measured against 288 real production files (0 false positives) before
landing here.

| Rule | CWE | Frameworks satisfied |
|---|---|---|
| SEC-CRYPTO-01 weak hash | CWE-327, CWE-1240 | FIPS-HR-01, PCI-DSS 6.2.4, NIST SC-13 |
| SEC-SECRET-01 hard-coded secret | CWE-798, CWE-259 | FIPS-HR-06, PCI-DSS 6.2.4, HIPAA-HR-04 |
| SEC-SQLI-01 SQL concatenation | CWE-89 | PCI-DSS 6.2.4, OWASP-HR-03 |
| SEC-DESER-01 unsafe deserialization | CWE-502 | OWASP-HR-06, STIG-HR-06 |
| SEC-CMDI-01 OS command injection | CWE-78 | OWASP-HR-03, STIG-HR-06 |
| SEC-TLS-01 TLS verification disabled | CWE-295 | FIPS-HR-04, PCI-DSS 4.2.1 |
| SEC-RANDOM-01 weak PRNG | CWE-338, CWE-330 | FIPS-HR-02 |

Each rule carries `metadata.qodo_rule_id` so the same rule set can later feed
Qodo's findings model directly instead of running as a separate status check.

## Setup

See [RUNBOOK.md](RUNBOOK.md).
