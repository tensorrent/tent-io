# LLT Governance and Evaluation Stack Whitepaper

This document is the technical completion record for the LLT governance/evaluation work implemented in this chat session on branch `stage-a-c-baseline-regression-gates`.

It lists:
- Exact files and locations,
- Workflow/job behavior,
- Script interfaces,
- Artifact contracts (JSON schema-style),
- Policy semantics and enforcement paths.

## 1) Scope and Repository
- Repository root: `tensorrent_tent_io_publish/`
- Primary workflow: `.github/workflows/tent-io-llt-expansion.yml`
- Primary domain: `tent_io/harness/` and `tent_io/harness/tools/`

## 2) Implemented Files (Created or Updated)

### 2.1 Workflow
- Updated: `.github/workflows/tent-io-llt-expansion.yml`

### 2.2 New harness scripts
- Added: `tent_io/harness/tools/check_baseline_drift.py`
- Added: `tent_io/harness/tools/check_regression.py`
- Added: `tent_io/harness/run_external_eval.py`
- Added: `tent_io/harness/tools/check_external_regression.py`
- Added: `tent_io/harness/tools/compute_promotion_decision.py`
- Added: `tent_io/harness/tools/summarize_promotion_decision_trend.py`

### 2.3 Additional planning document created in this chat
- Added (local doc artifact): `tent_io/docs/CODEX_AUTO_ANTIGRAVITY_EXECUTION_PLAN.md`

## 3) Commit Sequence for This Stack
(Omitted for brevity in documentation)

## 4) Workflow Contract
(See full specification in implementation)

## 5) Execution Flow (Expansion Job)
1. Validate inputs and profile selection.
2. Resolve split-gate profile to concrete thresholds.
3. Snapshot baseline pointer and previous sweep summary.
4. Execute expansion sweep and enforce internal guards (floor, immutability, regression).
5. External lane (external evaluate S1, S2, compare, decision state).
6. Baseline drift alarm (hard gate).
7. Promotion pointer step (policy-aware).
8. Write summaries and upload artifacts.

## 6) Script Interfaces
(See `tent_io/harness/tools/` for documentation in each script)
