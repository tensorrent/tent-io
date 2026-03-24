# Training Pipeline (MMLU + GSM8K)

This folder bootstraps local training/evaluation loops for Phase-1 intelligence work.

**How this connects to governance and benchmarks:** see `tent_io/docs/INTELLIGENCE_TEACHING_AND_TRAINING.md` (data → train → intelligence scoring → ODIN/TENT/GSM8K snapshot).

## 1) Prepare normalized corpora

```bash
python3 tent_io/harness/training/prepare_training_corpora.py
```

Optional GSM8K sources:

```bash
# Use local JSONL files
python3 tent_io/harness/training/prepare_training_corpora.py \
  --gsm8k-dir /path/to/gsm8k

# Or fetch from Hugging Face (requires datasets package)
python3 tent_io/harness/training/prepare_training_corpora.py \
  --download-gsm8k
```

Outputs are written to `tent_io/harness/fixtures/training/`.

## 2) Train MMLU baseline (NumPy)

```bash
python3 tent_io/harness/training/train_llt_baseline.py
```

This is a lightweight baseline to validate data plumbing and training loops before scaling to LLT/PyTorch.

## 2b) Train liquid language model (deterministic LLT-style)

```bash
python3 tent_io/harness/training/train_liquid_language_model.py --epochs 8
```

This script uses a liquid ODE-style hidden update and writes run artifacts under:

- `tent_io/harness/reports/training/liquid_llt_<timestamp>/`

By default it can replay deterministic Merkle-memory rows from:

- `tent_io/harness/reports/upg/upg_merkle_tensor_scroll.current.json`

By default it also mixes in deterministic conversational-logic rows for both train and test splits. Tune or disable with:

```bash
python3 tent_io/harness/training/train_liquid_language_model.py \
  --conversation-train-rows 256 \
  --conversation-test-rows 128 \
  --conversation-seed 17
```

Disable conversational-logic mix only when intentionally isolating MMLU-only behavior:

```bash
python3 tent_io/harness/training/train_liquid_language_model.py \
  --disable-conversational-logic
```

## 3) Evaluate GSM8K heuristic baseline

```bash
python3 tent_io/harness/training/eval_gsm8k_solver.py
```

If `gsm8k_test.jsonl` does not exist, run step 1 with `--gsm8k-dir` or `--download-gsm8k`.

## 4) Unified Phase-1 trainer (shared encoder, dual heads)

```bash
python3 tent_io/harness/training/train_unified_phase1.py --epochs 20
```

This script trains:
- MMLU head: 4-way multiple-choice classification
- GSM8K head: operation classification (`add/sub/mul/div/fallback`)

If GSM8K files are not present, it still trains/evaluates MMLU only.

By default this trainer also replays deterministic Merkle-memory rows from:

- `tent_io/harness/reports/upg/upg_merkle_tensor_scroll.current.json`

Disable when needed:

```bash
python3 tent_io/harness/training/train_unified_phase1.py \
  --disable-merkle-memory
```

Artifacts are saved per run under:

`tent_io/harness/reports/training/unified_phase1_<timestamp>/`

Each run writes:
- `model_weights.npz` (NumPy weights)
- `vocab.json` (token map)
- `report.json` (config, epoch logs, final metrics)

## 5) Compare runs (leaderboard)

```bash
python3 tent_io/harness/training/compare_runs.py --sort-by mmlu
```

Alternative ranking:

```bash
python3 tent_io/harness/training/compare_runs.py --sort-by gsm_answer
python3 tent_io/harness/training/compare_runs.py --sort-by gsm_op
```

Update stable best-run links and summary JSON:

```bash
python3 tent_io/harness/training/compare_runs.py \
  --sort-by mmlu \
  --update-best-links \
  --write-summary-json
```

This writes:
- `tent_io/harness/reports/training/leaderboard_summary.json`
- symlinks in `tent_io/harness/reports/training/`:
  - `best_mmlu`
  - `best_gsm_answer`
  - `best_gsm_op`

## 6) Deterministic replay of best checkpoint

```bash
python3 tent_io/harness/training/eval_best.py --best-link best_mmlu
```

For GSM-focused ranking (once GSM runs are available):

```bash
python3 tent_io/harness/training/eval_best.py --best-link best_gsm_answer
python3 tent_io/harness/training/eval_best.py --best-link best_gsm_op
```

## 7) Train voxel/vixel/vexel/boxels logic chains

Taxonomy used by these scripts:

- `voxel`: base structure (all are voxel-family structures)
- `vixel`: specialized bins in that structure
- `vexel`: outward polymorphic/public pixel representation of that structure
- `boxels`: full avatar polymorphic structure

```bash
python3 tent_io/harness/training/train_voxel_vixel_logic_chains.py --epochs 40
```

By default this trainer replays deterministic memory rows from:

- `tent_io/harness/reports/upg/upg_merkle_tensor_scroll.current.json`

This supports persistent Merkle reuse before new sample synthesis. Disable when needed:

```bash
python3 tent_io/harness/training/train_voxel_vixel_logic_chains.py \
  --disable-merkle-memory
```

Artifacts are written to:

`tent_io/harness/reports/training/voxel_stack_logic_<timestamp>/`

## 8) Compare voxel-stack runs

```bash
python3 tent_io/harness/training/compare_voxel_runs.py \
  --sort-by hybrid_step \
  --update-best-links \
  --write-summary-json
```

This writes:
- `tent_io/harness/reports/training/voxel_leaderboard_summary.json`
- symlinks:
  - `best_voxel_stack`
  - `best_voxel_hybrid_step`
  - `best_voxel_rule_step`

## 8b) Compare liquid language model runs

```bash
python3 tent_io/harness/training/compare_liquid_runs.py \
  --update-best-links \
  --write-summary-json
```

Alternative ranking keys:

```bash
python3 tent_io/harness/training/compare_liquid_runs.py --sort-by final_test_acc
python3 tent_io/harness/training/compare_liquid_runs.py --sort-by mmlu_test_acc
python3 tent_io/harness/training/compare_liquid_runs.py --sort-by conversational_logic_test_acc
```

This writes:
- `tent_io/harness/reports/training/liquid_leaderboard_summary.json`
- symlink:
  - `best_liquid_llt`

## 9) Evaluate best voxel-stack checkpoint

```bash
python3 tent_io/harness/training/eval_voxel_stack_best.py \
  --best-link best_voxel_hybrid_step
```

## 9b) Evaluate best liquid language checkpoint

```bash
python3 tent_io/harness/training/eval_liquid_language_model_best.py \
  --best-link best_liquid_llt
```

The evaluator uses the same conversational-logic test-row mix by default (`--conversation-test-rows`, `--conversation-seed`) unless `--disable-conversational-logic` is set.

Both training and best-checkpoint evaluation now report split metrics:

- MMLU subset accuracy (`final_mmlu_test_acc` / `mmlu_test_acc`)
- conversational-logic subset accuracy (`final_conversational_logic_test_acc` / `conversational_logic_test_acc`)
- combined test accuracy remains `final_test_acc` / `test_acc` for existing gates

Optional strict split gates are available in full pipeline/production wrapper:

- `--llt-min-mmlu-test-acc`
- `--llt-min-conversational-test-acc`
- `--llt-min-eval-mmlu-acc`
- `--llt-min-eval-conversational-acc`

These are disabled by default (`-1`) and can be enabled when you want fail-closed per-split quality thresholds.

For local one-toggle usage through `production_check.sh`, set:

- `LLT_SPLIT_GATE_PROFILE=strict_split_profile_v1`
- or `LLT_SPLIT_GATE_PROFILE=strict_split_profile_v1_conservative`

Calibrate split-gate floors from repeated production runs:

```bash
python3 tent_io/harness/calibrate_llt_split_gates.py --runs 5 --margin 0.01
```

Outputs:

- `tent_io/harness/reports/llt_split_gate_calibration.current.json`
- `tent_io/harness/reports/llt_split_gate_calibration.current.md`

In strict/production pipeline runs, this LLT replay is executed as a gated post-stage with `--llt-min-eval-acc` (default `0.20`). When LLT training is enabled in that run, replay targets the just-trained checkpoint directly; otherwise it evaluates `best_liquid_llt`. In strict mode with LLT training enabled, replay drift is also gated by `--llt-max-replay-drift` (default `1e-12`).

The evaluator auto-detects taxonomy profile from checkpoint metadata:

- legacy checkpoints -> legacy cue profile
- checkpoints with `stack_roles` -> voxel-family/public-vexel cue profile

## 10) Begin LLT expansion sweep

Run deterministic expansion profiles through the same production gates:

```bash
python3 tent_io/harness/run_llt_expansion_sweep.py --profiles expand_s1
```

Choose ranking target for "best profile" selection:

```bash
python3 tent_io/harness/run_llt_expansion_sweep.py --profiles expand_s1 --rank-by final_test_acc
python3 tent_io/harness/run_llt_expansion_sweep.py --profiles expand_s1 --rank-by mmlu_test_acc
python3 tent_io/harness/run_llt_expansion_sweep.py --profiles expand_s1 --rank-by conversational_logic_test_acc
```

Default `--rank-by` is `mmlu_test_acc` (same as CI workflow default).

Auto-select current top expansion pair:

```bash
python3 tent_io/harness/run_llt_expansion_sweep.py --profiles auto_top2
```

Manual CI option:

- Trigger `.github/workflows/tent-io-llt-expansion.yml` with `profiles` input (default `auto_top2`).
- Set `expansion_rank_by` (`final_test_acc`, `mmlu_test_acc`, `conversational_logic_test_acc`) to control sweep ranking target. CI default is `mmlu_test_acc`.
- Set `run_auto_all_compare=true` to also run `auto_all` and generate:
  - `tent_io/harness/reports/expansion/llt_expansion_baseline_change.current.json`
- Set `split_gate_profile` (`off`, `strict_split_profile_v1`, or `strict_split_profile_v1_conservative`) for one-toggle split-threshold preset in workflow runs.
- Set `min_best_final_test_acc` to enforce a fail-closed best-score floor in CI (default `0.20`).
- Set `min_delta_vs_previous_best` (for example `-0.02`) to enforce a fail-closed max allowed drop vs previous best.
- Set `promotion_history_keep_last` to trim promotion-history NDJSON retention in CI.
- Set `promotion_summary_top_k` to control leaderboard rows shown in Actions summaries (default `3`).
- Set `promotion_summary_sort_by` to choose leaderboard ordering (`promotions`, `avg_final_test_acc`, or `last_promoted_utc`).
- Set `promotion_summary_history_window` to summarize only the most recent N promotion events.
- CI validates dispatch inputs (numeric fields, sort key, non-empty query/profiles) and fails early on malformed values.
- CI also validates profile semantics before execution using `run_llt_expansion_sweep.py --validate-only`.
- Actions UI step summary reports best profile and trend sparkline
- CI writes a candidate pointer first and promotes it only after guards pass
- CI writes pointer-promotion audit JSON for each workflow job path
- CI also appends promotion lineage to:
  - `tent_io/harness/reports/expansion/llt_expansion_pointer_promotion_history.ndjson`
- CI emits profile-resolution JSON artifacts for each workflow job path
- CI baseline alarm fails closed when:
  - best profile changes from expected baseline (`expand_s2`)
  - best-profile train/eval drift exceeds configured max (default `0.0` in workflow alarm)
  - split-gate thresholds weaken below resolved profile floors

Promotion-history summary artifacts:

```bash
python3 tent_io/harness/summarize_llt_expansion_promotions.py
```

Recency-scoped summary:

```bash
python3 tent_io/harness/summarize_llt_expansion_promotions.py --history-window 200
```

Outputs:

- `tent_io/harness/reports/expansion/llt_expansion_pointer_promotion_summary.current.json`
- `tent_io/harness/reports/expansion/llt_expansion_pointer_promotion_summary.current.md`

These summary artifacts are also generated and uploaded by the LLT expansion workflow.

Example multi-profile expansion:

```bash
python3 tent_io/harness/run_llt_expansion_sweep.py \
  --profiles expand_s1,expand_s2,expand_s3,expand_s4,expand_s5
```

Outputs:

- sweep summary: `tent_io/harness/reports/expansion/llt_expansion_sweep.current.json`
- sweep summary (markdown): `tent_io/harness/reports/expansion/llt_expansion_sweep.current.md`
- sweep history (NDJSON): `tent_io/harness/reports/expansion/llt_expansion_history.ndjson`
- per-profile pipeline reports: `tent_io/harness/reports/expansion/full_stage_pipeline.<profile>.<sweep_run_id>.json`

The sweep summary also includes auto-ranking metadata:

- `best_profile`: top-ranked profile by gate pass count, then selected ranking metric (`--rank-by`), then `final_test_acc`, then lower drift
- ranking target can be changed with `--rank-by` while preserving gate-pass and drift ordering
- `ranking`: ordered compact profile comparison
- rolling pointer: `tent_io/harness/reports/expansion/llt_expansion_best.current.json`
- markdown trend section: recent best-score ASCII sparkline

Manual baseline-alarm check:

```bash
python3 tent_io/harness/check_llt_baseline_alarm.py \
  --summary tent_io/harness/reports/expansion/llt_expansion_sweep.current.json \
  --expected-profile expand_s2 \
  --max-train-eval-drift 0.0 \
  --require-train-gate-pass \
  --require-replay-gate-pass \
  --require-drift-gate-pass \
  --min-train-mmlu 0.205 \
  --min-train-conversational 0.130 \
  --min-eval-mmlu 0.205 \
  --min-eval-conversational 0.130
```
