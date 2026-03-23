# LLT Governance and Evaluation Stack Whitepaper

This document is the technical completion record for the LLT governance/evaluation work implemented on branch `stage-a-c-baseline-regression-gates` (and follow-on intelligence-layer wiring).

It lists:
- Exact files and locations,
- Workflow/job behavior,
- Script interfaces,
- Artifact contracts (JSON paths under `tent_io/harness/reports/`),
- Policy semantics and enforcement paths.

## 1) Scope and Repository
- Repository root: `tensorrent_tent_io_publish/`
- Primary workflow: `.github/workflows/tent-io-llt-expansion.yml`
- Primary domain: `tent_io/harness/` and `tent_io/harness/tools/`

## 2) Implemented Files (Index)

### 2.1 Workflow
- `.github/workflows/tent-io-llt-expansion.yml` — expansion sweep, external eval, promotion, intelligence gates, pointer promotion (see §4).

### 2.2 Promotion and drift (core gates)
| Path | Role |
|------|------|
| `tent_io/harness/tools/check_baseline_drift.py` | Compare baseline vs challenger for expansion pointer decisions. |
| `tent_io/harness/tools/check_regression.py` | Internal sweep regression vs previous summary. |
| `tent_io/harness/run_external_eval.py` | External evaluation entry (invoked by workflow steps). |
| `tent_io/harness/tools/check_external_regression.py` | External compare regression gate. |
| `tent_io/harness/tools/compute_promotion_decision.py` | Writes `promotion_decision.current.json` from internal + external artifacts. |
| `tent_io/harness/tools/summarize_promotion_decision_trend.py` | NDJSON history → trend summary for promotion decisions. |

### 2.3 Intelligence layer (scores, readiness, regression, advisory)
| Path | Role |
|------|------|
| `tent_io/harness/tools/compute_intelligence_scoring.py` | Sweep + optional external/promotion JSON → `intelligence_scoring.current.json`. |
| `tent_io/harness/tools/check_intelligence_readiness.py` | Floors on scores / decision state / contested ratio (optional enforcement). |
| `tent_io/harness/tools/check_intelligence_regression.py` | Point-in-time deltas vs previous scoring artifact. |
| `tent_io/harness/tools/summarize_intelligence_regression_trend.py` | Rolling alarm ratio / consecutive alarms from regression history. |
| `tent_io/harness/tools/compute_intelligence_promotion_advisory.py` | Combines readiness + regression + trend → advisory state (optional streak). |
| `tent_io/harness/tools/run_intel_benchmark_snapshot.py` | ODIN / GSM8K / TENT stub-or-CLI snapshot (separate from blended intelligence scores). |

### 2.4 Shared CLI inference (benchmark lanes)
- `tent_io/harness/cli_inference_harness.py` — single subprocess contract for ODIN and TENT v4.1 CLI mode (`--prompt`, `--question-id`); env resolution order documented in `CLI_BINARY_INFERENCE.md`.

### 2.5 Full-spectrum testing (scoring + harness)
| Path | Role |
|------|------|
| `tent_io/harness/intelligence_scoring_core.py` | Pure scoring v1.1 (`build_intelligence_scoring_output`); shared by `compute_intelligence_scoring.py` and tests. |
| `tent_io/harness/tests/test_*.py` | `unittest` suite: scoring golden vectors, CLI harness, regression `extract()`. |
| `tent_io/harness/tests/fixtures/sweep_full_spectrum.json` | Sample sweep JSON for fixture validation. |
| `tent_io/harness/tools/run_full_spectrum_harness.py` | Runs tests + fixture check; writes `harness/reports/full_spectrum_harness.current.json`. |
| `tent_io/docs/FULL_SPECTRUM_TESTING_AND_SCORING.md` | How to run tests and interpret scope. |

### 2.6 Planning and operator docs
- `tent_io/docs/CODEX_AUTO_ANTIGRAVITY_EXECUTION_PLAN.md`
- `tent_io/docs/INTELLIGENCE_TUNING.md` — workflow inputs and script knobs.
- `tent_io/docs/INTELLIGENCE_BENCHMARK_STATUS_AND_PLAN.md` — benchmark comparability scope.
- `tent_io/docs/INTELLIGENCE_TEACHING_AND_TRAINING.md` — data → train → scores → snapshot ordering.
- `tent_io/docs/CLI_BINARY_INFERENCE.md` — local executable env vars and flags.
- `tent_io/docs/FULL_SPECTRUM_TESTING_AND_SCORING.md` — unittest suite, scoring core, `run_full_spectrum_harness.py`.
- `tent_io/docs/PROMOTION_POLICY_GOVERNANCE.md` — contested vs aligned states, streak defaults, slot agreement policy.

## 3) Change Discipline
- Prefer **workflow_dispatch** or branch PRs that exercise `tent-io-llt-expansion.yml` so artifacts are produced under `tent_io/harness/reports/expansion/`.
- Treat **`*.current.json`** as **overwrite-per-run** outputs; history lives in **`*.history.ndjson`** or **`*.previous.current.json`** snapshots where implemented.
- Intelligence thresholds are **optional** until `enforce_*` inputs are set (see `INTELLIGENCE_TUNING.md`).

## 4) Workflow Contract (Artifacts)

**Authoritative behavior:** `.github/workflows/tent-io-llt-expansion.yml` (inputs, job conditions, upload list).

**Primary directory:** `tent_io/harness/reports/expansion/`

| Artifact | Purpose (as implemented) |
|----------|---------------------------|
| `llt_expansion_profiles_resolved.expansion_sweep.current.json` | Resolved profile thresholds for the sweep. |
| `llt_expansion_sweep.current.json` / `.md` | Expansion sweep summary; feeds intelligence scoring. |
| `llt_expansion_previous.current.json` | Prior sweep snapshot for regression checks. |
| `llt_expansion_baseline_before_expansion.current.json` | Baseline pointer before sweep (split-gate job). |
| `llt_expansion_best.candidate.json` | Candidate best pointer after sweep. |
| `llt_expansion_best.current.json` | Current promoted pointer. |
| `external_eval.expand_s1.current.json`, `external_eval.expand_s2.current.json` | Per-profile external eval payloads. |
| `external_eval_compare.current.json` | Paired compare; optional `external_eval_compare.previous.json`. |
| `promotion_decision.current.json` | Decision state + `promotion_allowed`; `promotion_decision.history.ndjson` |
| `promotion_decision_trend.current.json` / `.md` | Trend over promotion history. |
| `intelligence_scoring.current.json` / `.md` | Blended scores from `compute_intelligence_scoring.py`; `intelligence_scoring.previous.current.json` for deltas. |
| `intelligence_regression.current.json` | Point regression vs previous scoring. |
| `intelligence_regression.history.ndjson` | Regression history append. |
| `intelligence_regression_trend.current.json` / `.md` | Rolling trend summary. |
| `intelligence_readiness.current.json` | Readiness gate output. |
| `intelligence_promotion_advisory.current.json` / `.md` | Advisory merge; `intelligence_promotion_advisory.history.ndjson` |
| `llt_expansion_pointer_promotion*.json` / `.ndjson` | Pointer promotion audit trail (job-specific suffixes may include `expansion_sweep` or `auto_all`). |

**Workflow inputs** for intelligence (non-exhaustive): `intelligence_scoring_preset`, `enforce_intelligence_readiness`, `enforce_intelligence_regression`, `enforce_intelligence_regression_trend`, `enforce_intelligence_promotion_advisory`, `intelligence_advisory_required_streak`, and optional numeric floors/deltas — see workflow `inputs:` block and `INTELLIGENCE_TUNING.md`.

## 5) Execution Flow (Expansion Job)
1. Validate inputs and profile selection.
2. Resolve split-gate profile to concrete thresholds.
3. Snapshot baseline pointer and previous sweep summary.
4. Execute expansion sweep and enforce internal guards (floor, immutability, regression).
5. External lane (external evaluate S1, S2, compare, decision state).
6. Baseline drift alarm (hard gate).
7. Intelligence scoring, readiness, regression, trend, advisory (as enabled in workflow).
8. Promotion pointer step (policy-aware).
9. Write summaries and upload artifacts.

## 6) Script Interfaces (`tent_io/harness/tools/`)

Each script supports `--help`. High-level map:

| Script | Typical inputs | Typical outputs |
|--------|----------------|-----------------|
| `compute_intelligence_scoring.py` | `--sweep-summary`, optional `--external-compare`, `--promotion-decision`, `--promotion-trend`, `--scoring-preset` | `--out-json`, `--out-md` |
| `check_intelligence_readiness.py` | `--score-json`, optional floors / flags | `--out` JSON |
| `check_intelligence_regression.py` | `--current`, `--previous` | `--out`, optional `--history-out` |
| `summarize_intelligence_regression_trend.py` | `--history` | `--out-json`, `--out-md` |
| `compute_intelligence_promotion_advisory.py` | `--promotion-decision`, readiness/regression paths | `--out-json`, `--out-md`, `--history-out` |
| `run_intel_benchmark_snapshot.py` | `--skip-*`, optional `--tent-v41-cli` | `intel_benchmark_snapshot.current.json` under `harness/reports/` |

Promotion/drift/regression scripts follow paths wired in `tent-io-llt-expansion.yml` (§4).

## 7) Teaching, training, and the evaluation loop
- **Map (data → train → governance scores → benchmarks):** `tent_io/docs/INTELLIGENCE_TEACHING_AND_TRAINING.md`
- **Training commands and Phase-1 scripts:** `tent_io/harness/training/README.md`
- **Scoring knobs:** `tent_io/docs/INTELLIGENCE_TUNING.md`
- **Benchmark scope:** `tent_io/docs/INTELLIGENCE_BENCHMARK_STATUS_AND_PLAN.md`

Teaching signals in-repo include normalized corpora (`prepare_training_corpora.py`), optional conversational-logic and Merkle mixes in selected trainers, and governance-derived weights via expansion artifacts and `compute_intelligence_scoring.py` (as implemented).

## 8) Related: local harness reports (non-expansion)
- Benchmark snapshot: `tent_io/harness/reports/intel_benchmark_snapshot.current.json` and `.md` (from `run_intel_benchmark_snapshot.py`).
- Full-spectrum test run: `tent_io/harness/reports/full_spectrum_harness.current.json` (from `run_full_spectrum_harness.py`; see `FULL_SPECTRUM_TESTING_AND_SCORING.md`).
