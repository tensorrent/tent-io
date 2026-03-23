# Intelligence: teaching, training, and evaluation loop

This document ties **data → train → governance metrics → benchmarks** as implemented under `tent_io/harness/`. It is a **roadmap and wiring map**, not a claim about parity with external leaderboards.

## 1) What “teaching” means here

- **Corpus teaching:** normalized JSONL rows (MMLU, GSM8K) plus optional **synthetic conversational-logic** rows and **Merkle-replay** rows mixed into some trainers (`train_liquid_language_model.py`, `train_unified_phase1.py`). These are **in-harness** mixes for loop validation and ablations.
- **Governance teaching:** expansion sweeps and scoring scripts encode **what to reward** (accuracy, drift, replay consistency, external-compare alignment). See `INTELLIGENCE_TUNING.md` for knobs.

## 2) Data preparation

| Step | Script | Output (default layout) |
|------|--------|-------------------------|
| Normalize MMLU + optional GSM8K | `tent_io/harness/training/prepare_training_corpora.py` | `tent_io/harness/fixtures/training/*.jsonl` |

```bash
python3 tent_io/harness/training/prepare_training_corpora.py \
  --mmlu-dir /path/to/mmlu/data \
  --download-gsm8k
```

You must supply a real **`--mmlu-dir`** (HELM-style split folders `dev/`, `test/`, `val/` with CSVs). GSM8K is optional for the snapshot lane; use `--gsm8k-dir` or `--download-gsm8k`.

## 3) Training entry points (Phase-1 family)

Detailed commands: **`tent_io/harness/training/README.md`**.

| Script | Role |
|--------|------|
| `train_llt_baseline.py` | Lightweight MMLU baseline; validates plumbing. |
| `train_liquid_language_model.py` | Liquid-style hidden update; optional conversational-logic mix + Merkle rows. |
| `train_unified_phase1.py` | Shared encoder, MMLU + GSM heads; optional Merkle mix. |
| `train_voxel_vixel_logic_chains.py` | Separate logic-chain experiment path (see script docstrings). |

Artifacts land under `tent_io/harness/reports/training/` (per-script naming).

## 4) From training metrics to “intelligence” scores

1. **Expansion sweep** produces a summary JSON with `best_profile` (test accuracies, replay, drift).  
2. **`compute_intelligence_scoring.py`** consumes that summary (and optional external-compare / promotion JSON) and emits **`intelligence_scoring.current.json`** (via CI or local run).  
3. Formula details: ask in-repo **`compute_intelligence_scoring.py`** and `INTELLIGENCE_TUNING.md` (presets: `default` vs `conversation_focused`).

Benchmark lanes (**ODIN**, **TENT v4.1**, **GSM8K heuristic**) are **separate** from those blended scores; see `INTELLIGENCE_BENCHMARK_STATUS_AND_PLAN.md`.

## 5) Recommended expansion order (operator)

1. **Corpora** — `prepare_training_corpora.py` until `mmlu_*.jsonl` exist; add GSM8K if you want the heuristic eval lane.  
2. **Train** — pick one trainer; keep run artifacts versioned.  
3. **Sweep / scoring** — run the expansion workflow or local sweep so `llt_expansion_sweep.current.json` and `intelligence_scoring.current.json` exist.  
4. **Benchmark snapshot** — `tent_io/harness/tools/run_intel_benchmark_snapshot.py` (optional CLI: `CLI_BINARY_INFERENCE.md`).  
5. **Tune** — adjust `intelligence_scoring_preset`, readiness floors, regression thresholds per `INTELLIGENCE_TUNING.md`.

## 6) Related documents

| Doc | Topic |
|-----|--------|
| `tent_io/harness/training/README.md` | Commands and defaults for trainers. |
| `INTELLIGENCE_TUNING.md` | Scoring presets, readiness, regression, advisory. |
| `INTELLIGENCE_BENCHMARK_STATUS_AND_PLAN.md` | What is comparable vs in-harness only. |
| `CLI_BINARY_INFERENCE.md` | Local executable contract for ODIN / TENT lanes. |
| `LLT_GOVERNANCE_AND_EVAL_STACK_WHITEPAPER.md` | Workflow, artifact registry under `harness/reports/expansion/`, and tool index. |
| `FULL_SPECTRUM_TESTING_AND_SCORING.md` | Scoring core tests, CLI harness tests, `run_full_spectrum_harness.py`. |
