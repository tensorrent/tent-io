# SEGGCI + OmniForge Integration

This integration binds:

1. **SparsePlug** deterministic profile decisions,
2. **SEGGCI** runtime reasoning state,
3. **RYS** convergence stage (deterministic fallback adapter),
4. **OmniForge** seed compilation.

## Orchestrator

- `tent_io/harness/run_seggci_omniforge_stack.py`

## Flow

```text
SparsePlug decision JSON
  -> schema/hash validation
  -> deterministic runtime env projection
  -> SEGGCI reason/status execution
  -> RYS fixed-point convergence metrics (depth/stability/hash)
  -> OmniForge seed compile from deterministic payload
  -> auditable run manifest
```

## Command

```bash
python3 tent_io/harness/run_seggci_omniforge_stack.py \
  --query "system profile check" \
  --strict
```

Include Bingo stage when available:

```bash
python3 tent_io/harness/run_seggci_omniforge_stack.py \
  --query "system profile check" \
  --with-bingo
```

Run all stages (decision -> validation -> orchestrator) in one command:

```bash
python3 tent_io/harness/run_full_stage_pipeline.py --with-bingo
```

Production alias (recommended for CI):

```bash
python3 tent_io/harness/run_full_stage_pipeline.py --production
```

CI wrapper options:

```bash
bash tent_io/harness/production_check.sh
```

or

```bash
make production-check
```

Wrapper environment knobs include:

- voxel gates: `VOXEL_MIN_HYBRID_STEP_ACC`, `VOXEL_MIN_STACK_ACC`
- LLT stage: `LLT_EPOCHS`, `LLT_HIDDEN_DIM`, `LLT_MAX_TRAIN`, `LLT_MAX_TEST`, `LLT_MIN_TEST_ACC`, `LLT_MIN_EVAL_ACC`, `LLT_MAX_REPLAY_DRIFT`
- LLT conversational-logic mix: `CONVERSATION_TRAIN_ROWS`, `CONVERSATION_TEST_ROWS`, `CONVERSATION_SEED`, `DISABLE_CONVERSATIONAL_LOGIC`
- optional LLT split gates (disabled by default with `-1`): `LLT_MIN_MMLU_TEST_ACC`, `LLT_MIN_CONVERSATIONAL_TEST_ACC`, `LLT_MIN_EVAL_MMLU_ACC`, `LLT_MIN_EVAL_CONVERSATIONAL_ACC`
- local split-gate profile preset: `LLT_SPLIT_GATE_PROFILE` (`off`, `strict_split_profile_v1`, or `strict_split_profile_v1_conservative`)
- local drift history maintenance (optional): `LLT_DRIFT_AUTO_LOG`, `LLT_DRIFT_HISTORY_PATH`, `LLT_DRIFT_KEEP_LAST`

Branch protection setup guide:

- `tent_io/docs/BRANCH_PROTECTION_PRODUCTION_GATE.md`

Antigravity V46 context crosswalk (presence check against imported build):

```bash
python3 tent_io/harness/verify_antigravity_blueprint_v46.py
```

Output:

- `tent_io/harness/reports/antigravity_v46_blueprint_check.current.json`

Auto-priority merge plan from that crosswalk:

```bash
python3 tent_io/harness/generate_antigravity_v46_merge_plan.py
```

Outputs:

- `tent_io/harness/reports/antigravity_v46_merge_plan.current.json`
- `tent_io/harness/reports/antigravity_v46_merge_plan.current.md`

Include voxel/vixel/vexel/boxels post-stage evaluation:

```bash
python3 tent_io/harness/run_full_stage_pipeline.py \
  --with-voxel-eval \
  --voxel-best-link best_voxel_hybrid_step
```

Voxel-family taxonomy used in training/eval artifacts:

- `voxel`: base structure (all are voxel-family structures)
- `vixel`: specialized bins within the voxel structure
- `vexel`: outward polymorphic pixel/public representation
- `boxels`: full avatar polymorphic structure

Strict/production mode runs voxel evaluation by default and enforces gates:

- `hybrid_step_acc >= 0.60`
- `stack_acc >= 0.65`

You can override thresholds:

```bash
python3 tent_io/harness/run_full_stage_pipeline.py \
  --strict \
  --voxel-min-hybrid-step-acc 0.58 \
  --voxel-min-stack-acc 0.62
```

Use `--skip-voxel-eval` only when intentionally bypassing the quality gate.
You can also set threshold env vars for the wrapper (`VOXEL_MIN_HYBRID_STEP_ACC`, `VOXEL_MIN_STACK_ACC`).

Strict/production mode also runs liquid language training by default and enforces:

- `final_test_acc >= 0.20` (default gate)
- LLT train/eval include a deterministic conversational-logic row mix by default (configurable row counts and seed)
- LLT outputs include split metrics for visibility: MMLU subset accuracy and conversational-logic subset accuracy (alongside combined gate metric)

Strict/production mode also runs deterministic LLT best-checkpoint replay and enforces:

- `test_acc >= 0.20` (default replay gate)
- replay target defaults to the checkpoint trained in the same pipeline run; if LLT training is skipped, replay falls back to `best_liquid_llt`
- when LLT training is enabled in the same run, replay drift must satisfy `abs(replay_test_acc - train_final_test_acc) <= 1e-12` (default)

You can tune LLT gate/runtime with:

- `--llt-epochs`
- `--llt-hidden-dim`
- `--llt-max-train`
- `--llt-max-test`
- `--llt-min-test-acc`
- `--llt-min-eval-acc`
- `--llt-max-replay-drift`
- `--conversation-train-rows`
- `--conversation-test-rows`
- `--conversation-seed`
- `--disable-conversational-logic` (intentional bypass only)
- `--llt-min-mmlu-test-acc` (default `-1`, disabled)
- `--llt-min-conversational-test-acc` (default `-1`, disabled)
- `--llt-min-eval-mmlu-acc` (default `-1`, disabled)
- `--llt-min-eval-conversational-acc` (default `-1`, disabled)
- `--skip-llt-train` (intentional bypass only)
- `--skip-llt-eval` (intentional bypass only)

To calibrate split-gate floors from observed runs before enabling strict split thresholds:

```bash
python3 tent_io/harness/calibrate_llt_split_gates.py --runs 5 --margin 0.01
```

For audit logging and CI assertion from the pipeline report:

```bash
python3 tent_io/harness/log_llt_drift_history.py \
  --report tent_io/harness/reports/full_stage_pipeline.current.json \
  --out tent_io/harness/reports/llt_drift_history.ndjson \
  --require-drift-pass
```

Trim local drift history to last N rows:

```bash
python3 tent_io/harness/trim_llt_drift_history.py \
  --path tent_io/harness/reports/llt_drift_history.ndjson \
  --keep-last 200
```

To begin LLT expansion while preserving the same strict gates and drift checks:

```bash
python3 tent_io/harness/run_llt_expansion_sweep.py --profiles expand_s1
```

Available built-in profiles: `expand_s1` through `expand_s5`. The sweep summary includes `best_profile` and `ranking` for quick profile selection.
Sweep outputs include JSON/markdown summaries plus NDJSON history with a recent-score trend sparkline.

Alias shortcuts:

- `auto_top2` -> `expand_s2,expand_s4`
- `auto_all` -> `expand_s1,expand_s2,expand_s3,expand_s4,expand_s5`

Manual CI trigger is available via workflow:

- `.github/workflows/tent-io-llt-expansion.yml`
- optional input `run_auto_all_compare=true` runs `auto_all` and emits baseline change artifact:
  - `tent_io/harness/reports/expansion/llt_expansion_baseline_change.current.json`
- optional input `expansion_rank_by` controls sweep best-profile ranking target (`final_test_acc`, `mmlu_test_acc`, or `conversational_logic_test_acc`); workflow default is `mmlu_test_acc`
- optional input `min_best_final_test_acc` enforces a fail-closed floor on `best_profile.final_test_acc` (default `0.20`)
- optional input `min_delta_vs_previous_best` enforces a fail-closed floor on score delta vs previous best (example `-0.02` allows up to 2 points drop)
- optional input `promotion_history_keep_last` trims promotion-history NDJSON to last N rows
- optional input `promotion_summary_top_k` controls how many leaderboard rows are shown in step summary tables (default `3`)
- optional input `promotion_summary_sort_by` controls leaderboard ordering (`promotions`, `avg_final_test_acc`, or `last_promoted_utc`)
- optional input `promotion_summary_history_window` limits leaderboard summary to the most recent N promotion events
- optional input `split_gate_profile` applies split-threshold preset (`off`, `strict_split_profile_v1`, or `strict_split_profile_v1_conservative`) in expansion workflows
- workflow validates dispatch inputs early (numeric fields, sort key, and non-empty query/profiles) and fails fast on invalid values
- workflow also validates profile semantics through `run_llt_expansion_sweep.py --validate-only` before execution
- workflow step summaries include best profile, key metrics, and trend sparkline
- workflow step summaries also include guard telemetry (floor and delta checks)
- workflow baseline alarm fails closed before pointer promotion when baseline profile, drift, or split-threshold expectations are violated
- CI updates best-pointer in two phases (candidate -> promote) so failing guards do not overwrite the current pointer
- pointer promotion audit artifacts are emitted per job path:
  - `tent_io/harness/reports/expansion/llt_expansion_pointer_promotion.expansion_sweep.current.json`
  - `tent_io/harness/reports/expansion/llt_expansion_pointer_promotion.auto_all.current.json`
- pointer promotion appends to NDJSON history:
  - `tent_io/harness/reports/expansion/llt_expansion_pointer_promotion_history.ndjson`
- profile-resolution audit artifacts are emitted per workflow job path:
  - `tent_io/harness/reports/expansion/llt_expansion_profiles_resolved.expansion_sweep.current.json`
  - `tent_io/harness/reports/expansion/llt_expansion_profiles_resolved.auto_all.current.json`

Local sweep ranking target can also be set directly:

```bash
python3 tent_io/harness/run_llt_expansion_sweep.py --profiles auto_top2 --rank-by mmlu_test_acc
```

Default local `--rank-by` is `mmlu_test_acc` (aligned with workflow default).

Local baseline alarm check:

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

Promotion leaderboard summary (JSON + markdown):

```bash
python3 tent_io/harness/summarize_llt_expansion_promotions.py
```

Optional recency window:

```bash
python3 tent_io/harness/summarize_llt_expansion_promotions.py --history-window 200
```

The LLT expansion workflow also generates and uploads these leaderboard summaries each run.

UPG training/teaching export now runs as a post stage by default and writes:

- `tent_io/harness/reports/upg/upg_training_record.current.json`
- `tent_io/harness/reports/upg/upg_training_record.current.json.gz`

This record includes hashed references to stage outputs and recent training reports, plus a deterministic prime/Ulam projection for UPG ingestion.
Use `--skip-upg-export` only when intentionally bypassing this export.

UPG -> MIDI persistent memory export also runs by default after UPG export:

- `tent_io/harness/reports/upg/upg_prime_pins.current.mid`
- `tent_io/harness/reports/upg/upg_prime_pins_scroll.current.ndjson`
- `tent_io/harness/reports/upg/upg_prime_pins_manifest.current.json`

The exporter maps prime/Ulam projection points into deterministic note pins (cylinder metaphor) and writes an append-only hashed scroll (`meta_memory`, `note_on`, `note_off`) for replay/audit.
Use `--skip-midi-scroll-export` only when intentionally bypassing this export.

Merkle bit-hash tensor-scroll export runs after MIDI scroll export:

- `tent_io/harness/reports/upg/upg_merkle_tensor_scroll.current.json`
- `tent_io/harness/reports/upg/upg_merkle_tensor_scroll_wireframe.current.md`

This stage computes an ordered Merkle root over scroll event hashes, emits bucketed bit-hash map rows, verifies invariants (hash-chain continuity and event-hash integrity), and writes synthesis instructions for persistent replay.
Cache reuse is enabled by default (same scroll hash -> reuse map); disable with `--no-merkle-cache-reuse`.
Use `--skip-merkle-scroll-export` only when intentionally bypassing this export.

Output manifest:

- `tent_io/harness/reports/seggci_omniforge_run.current.json`

## Manifest Guarantees

- stage-level statuses and errors
- SparsePlug decision hash and selected profile
- SEGGCI status + reasoning keys
- OmniForge seed output metadata
- run-level deterministic hash (`run_hash`)

## Notes

- If `--strict` or `--production` is used, stage failure returns non-zero exit.
- Without strict mode, manifest still records partial/failure states for audit continuity.
