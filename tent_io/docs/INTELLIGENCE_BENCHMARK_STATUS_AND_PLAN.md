# Intelligence Benchmark Status and Plan

## What “standard benchmarks” means here

- **Frontier API benchmarks** (full MMLU, MMLU-Pro, GPQA at scale) require a **real inference backend** and **licensed or downloaded datasets**. This repo includes **lanes** for that (`odin_real_benchmark.py`, `tent_v41_external_benchmark/`), not a single command that replaces industry leaderboards.
- **In-repo snapshot** (`tent_io/harness/tools/run_intel_benchmark_snapshot.py`) reports:
  - **Internal harness** metrics from existing expansion/scoring artifacts (if present).
  - **ODIN** on `fixtures/mmlu_pro_sample.json` (accuracy is meaningful only when `ANTIGRAVITY_INFERENCE_URL` is set or a CLI binary is resolved via `cli_inference_harness`; **stub ⇒ not comparable**).
  - **GSM8K heuristic** via `eval_gsm8k_solver.py` (baseline heuristic, not the LLT unless you wire the model).
  - **TENT v4.1 adapter** on built-in questions; default **`TENT_INFERENCE_PATTERN=stub`** (pipeline check). For a local executable, see **`tent_io/docs/CLI_BINARY_INFERENCE.md`** and run with **`--tent-v41-cli`**.

Run locally:

```bash
python3 tent_io/harness/tools/run_intel_benchmark_snapshot.py
```

Artifacts:

- `tent_io/harness/reports/intel_benchmark_snapshot.current.json`
- `tent_io/harness/reports/intel_benchmark_snapshot.current.md`

For **corpus prep → training → expansion/scoring** ordering, see **`INTELLIGENCE_TEACHING_AND_TRAINING.md`**.

## Where things stand (conceptual)

| Layer | What it measures | Comparable to “frontier”? |
|------|------------------|---------------------------|
| LLT expansion + intelligence scoring | Internal MMLU-style, conversational, drift, governance-derived scores | No — **in-harness** as implemented |
| `run_external_eval.py` | Proxy metrics from pipeline + optional benchmark JSON | Only if you pass a real **benchmark-summary** artifact |
| ODIN / TENT v4.1 bundle | MMLU-Pro / GPQA-style Q&A with local inference | Yes **in principle**, once engine + dataset + run are configured |
| GSM8K heuristic | Arithmetic heuristics on JSONL | Baseline only |

## Plan to continue (recommended order)

1. **Establish a baseline snapshot** after a full pipeline or CI run so `llt_expansion_sweep.current.json` and `intelligence_scoring.current.json` exist; re-run the snapshot script.
2. **Wire real inference** for ODIN or TENT v4.1 (HTTP or one CLI binary via `cli_inference_harness`; see `tent_io/docs/CLI_BINARY_INFERENCE.md`), then rerun on **`mmlu_pro_sample`** → expand to HF-fetched sets per `tent_v41_external_benchmark/README.md`.
3. **Pass benchmark summaries** into `run_external_eval.py` so proxy lanes align with measured external JSON.
4. **Track over time** using existing intelligence regression + advisory artifacts; treat benchmark accuracy as **another input** to the same governance envelope.

## Tuning reference

See `tent_io/docs/INTELLIGENCE_TUNING.md` for scoring presets, readiness, and advisory streaks.
