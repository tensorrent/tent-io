# CODEX AUTO-ANTIGRAVITY EXECUTION PLAN

This plan formalizes the auto-governance layer for LLT Expansion, ensuring that all promotions are backed by deterministic regression checks and external evaluation alignment.

## 1. Regression-Gated Expansion
- All expansion sweeps must pass the `check_regression.py` guard.
- If a regression in `final_test_acc` or `mmlu_test_acc` is detected, the run is marked ALARM and blocked.

## 2. External Evaluation Alignment
- The `run_external_eval.py` proxy provides a secondary validation signal.
- Promotion is only "Ready" if the internal best profile aligns with the external favored profile for `N` consecutive runs (default N=1).

## 3. Enforcement Policy
- Policy enforcement is optional and controlled by workflow inputs.
- When `enforce_promotion_decision_policy` is enabled, the system will actively skip pointer updates if the decision state is not `aligned_ready_for_promotion`.

## 4. Visibility and Audit
- All decision states and trends are captured in `promotion_decision.history.ndjson`.
- Pre-alarm snapshots provide visibility into the decision state even if a hard-gate alarm (like baseline drift) occurs later in the job.
