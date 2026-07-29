# Qodo + Opengrep Quality Gate Demo

Two independent gates on one PR. Both must pass before a merge is possible.

| Gate | Mechanism | Catches | Determinism |
|---|---|---|---|
| **Opengrep** | CI required **status check** | syntactic floor: banned APIs, dangerous literals, unsafe shapes | same commit -> identical findings, every run |
| **Qodo** | **REQUEST_CHANGES review** vote | judgment: authorization, business logic, exploitability | LLM reasoning, non-reproducible by design |

Branch protection ANDs them. They are different provider primitives -- a status
check and a review vote -- so they compose without interfering.

## The point of this demo

The two gates are **complementary, not redundant**. Three PRs prove it:

| PR | Defect | Opengrep | Qodo | Merge |
|---|---|---|---|---|
| 1 | `hashlib.md5()` for password storage | **FAIL** | flags it too | **BLOCKED** |
| 2 | ownership check removed from `get_invoice` | **PASS** (cannot express it) | **REQUEST_CHANGES** | **BLOCKED** |
| 3 | harmless refactor | PASS | APPROVE | **MERGEABLE** |

PR 2 is the one that matters. A pattern matcher has no way to know that
`get_invoice` is supposed to enforce record ownership -- there is no banned API
and no dangerous literal, just a missing check. Opengrep is silent and correct
to be silent. Qodo catches it.

PR 1 is the inverse: Opengrep decides it mechanically and identically on every
run, which is what an auditor wants as evidence.

Neither gate replaces the other. That is the whole architecture.

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
