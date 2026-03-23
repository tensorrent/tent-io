# Intelligence Layer Tuning

This document lists operator-tunable knobs for the LLT intelligence stack. Scope: as implemented in `tent_io/harness/tools/` and `.github/workflows/tent-io-llt-expansion.yml`.

For **benchmark posture** (what is comparable vs in-harness only) and a continuation plan, see `INTELLIGENCE_BENCHMARK_STATUS_AND_PLAN.md`.

For **teaching/training expansion ordering** (data → train → scores → snapshot), see `INTELLIGENCE_TEACHING_AND_TRAINING.md`.

For **full-spectrum unittest + scoring fixture validation**, see `FULL_SPECTRUM_TESTING_AND_SCORING.md`.

For **promotion decision states** (contested vs aligned, streaks), see `PROMOTION_POLICY_GOVERNANCE.md`.

## Scoring weights

- **Script:** `tent_io/harness/tools/compute_intelligence_scoring.py`
- **CLI:** `--scoring-preset default|conversation_focused`
- **Workflow input:** `intelligence_scoring_preset` (same values)
- **`default`:** Original ml/logic weighting (documented in artifact `weight_presets`).
- **`conversation_focused`:** Raises weight on conversational and replay-consistency terms for `logic_chain_score` and `ml_intelligence_score` (see emitted JSON `weight_presets`).

## Readiness thresholds

- **Script:** `tent_io/harness/tools/check_intelligence_readiness.py`
- Optional floors and governance filters via workflow inputs (`intelligence_min_*`, `intelligence_max_contested_ratio`, `intelligence_allowed_decision_states`).
- Empty inputs disable that check.

## Regression and trend

- **Point deltas:** `check_intelligence_regression.py` — thresholds via `intelligence_min_delta_*`, `intelligence_max_delta_contested_ratio`.
- **Sustained degradation:** `summarize_intelligence_regression_trend.py` — `intelligence_regression_trend_window`, `intelligence_regression_max_alarm_ratio`, `intelligence_regression_max_consecutive_alarms`.

## Advisory and promotion

- **Script:** `tent_io/harness/tools/compute_intelligence_promotion_advisory.py`
- **`skipped` signals:** Regression/trend/readiness may report `skipped` (e.g. no prior run). Advisory treats `ok` and `skipped` as acceptable for `promote_candidate` base state; `alarm` still blocks.
- **Streak:** `intelligence_advisory_required_streak` — consecutive `promote_candidate` base states before final `advisory_state` becomes `promote_candidate` (workflow default **2**; see `PROMOTION_POLICY_GOVERNANCE.md`).
- **Enforcement:** `enforce_intelligence_promotion_advisory` requires `advisory_state=promote_candidate` before pointer promotion (with external eval enabled).

## Recommended tuning order

1. Run with enforcement off; record artifacts for several runs.
2. Set `intelligence_scoring_preset` if conversational signal should weigh higher.
3. Set readiness thresholds from observed score ranges (avoid empty floors until stable).
4. Enable regression deltas, then trend limits, then advisory streak, then promotion advisory enforcement.
