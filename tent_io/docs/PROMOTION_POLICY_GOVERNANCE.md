# Promotion policy and decision states

**Scope:** As implemented in `tent_io/harness/tools/compute_promotion_decision.py`, `compute_intelligence_promotion_advisory.py`, and `.github/workflows/tent-io-llt-expansion.yml`. This document is operator-facing policy text, not a proof about model quality.

## What “signals disagree” means

- **Internal signal:** `best_profile.profile` from `llt_expansion_sweep.current.json` (canonical expand slot, e.g. `expand_s1`, `expand_s2`).
- **External signal:** `favored_profile` from `external_eval_compare.current.json` (`expand_s1` | `expand_s2` | `tie_or_missing`).

If both are `expand_s1` or `expand_s2` and **internal slot ≠ external favored slot**, the decision is **`contested`**. In that state **`promotion_allowed` is false** (no silent dominance by either axis).

## Decision states (promotion script)

| `decision_state` | Meaning (as implemented) |
|------------------|---------------------------|
| `aligned_ready_for_promotion` | Slots agree, margins met, aligned streak ≥ `alignment_required_runs`. |
| `aligned_pending_confirmation` | Slots agree; streak not yet at `alignment_required_runs`. |
| `aligned_but_margin_insufficient` | Slots agree; streak ok but internal or external margin below threshold. |
| `contested` | Internal profile slot and external favored slot disagree (or name fallback mismatch). `promotion_allowed` is false unless tie-break overrides (below). |
| `contested_external_override` | **Optional**, only if `--contested-external-tie-break`: same contested slot mismatch, but aggregate external margin ≥ threshold, margin sign matches `favored_profile`, external tie-break streak ≥ required, and `train_eval_drift` ≈ 0 (unless `--tie-break-relax-drift-check`). Does **not** relax regression or readiness gates downstream. |
| `insufficient_signal` | Missing internal profile, unresolved external favor (`tie_or_missing`), or unknown external token. |

## Alignment streak reset

`aligned_streak` counts **consecutive runs with `aligned: true`**. After a **contested** or **insufficient** run, the next aligned run starts at **1** (contested does not count toward alignment).

## Contested external tie-break (optional, off by default)

Workflow inputs: `contested_external_tie_break` (boolean), `contested_external_margin_threshold`, `contested_external_tie_break_streak`.

CLI (key flags): `compute_promotion_decision.py --contested-external-tie-break --tie-break-margin-floor … --tie-break-agreement-floor … --tie-break-confidence-threshold … --external-tie-break-streak-required …`

### Aggregate margin

External margin is the difference of **mean** of `mmlu_pro_acc`, `gpqa_acc`, `long_context_acc`, `consistency_score` between `expand_s1` and `expand_s2` blocks in `external_eval_compare.current.json`. The favored profile must match the **sign** of that aggregate (e.g. `expand_s1` ⇒ margin &gt; 0).

### Per-metric agreement (directional coherence)

For each metric, delta = s1−s2 (from `deltas_s1_minus_s2` if present, else computed from metrics). **Agreement ratio** = fraction of **nonzero** deltas that point in the favored direction (`expand_s1` ⇒ delta &gt; 0, `expand_s2` ⇒ delta &lt; 0).

**Safety floors** (before confidence): `agreement_ratio` must be ≥ `--tie-break-agreement-floor` (default **0.6**); `|aggregate margin|` must be ≥ `--tie-break-margin-floor` (default **0.01**). Otherwise tie-break stays blocked with reasons such as `low_metric_agreement` or `margin_too_small`.

### Confidence (0–1)

When floors pass, **tie-break confidence** is a weighted sum (defaults):

`0.35·M + 0.25·S + 0.25·A + 0.15·D`

- **M** = `min(|aggregate margin| / tie_break_target_margin, 1)` (default target **0.03**)
- **S** = `min(external_tie_break_streak / streak_required, 1)`
- **A** = agreement ratio
- **D** = drift stability from `train_eval_drift` vs `--tie-break-drift-tol`, or **1.0** if `--tie-break-relax-drift-check`

Override promotion is allowed only if **confidence ≥ `--tie-break-confidence-threshold`** (default **0.75**), in addition to contested slot mismatch and tie-break mode enabled.

Artifacts include `tie_break_confidence`, `tie_break_confidence_components`, and `external_metric_agreement_ratio`.

### Adaptive tie-break threshold (optional)

When `--tie-break-adaptive-threshold` is set (workflow input `tie_break_adaptive_threshold`):

1. Read prior NDJSON rows with `decision_state == "contested"` and a numeric `tie_break_confidence` (last `--tie-break-adaptive-window` values, default 20).
2. If at least `--tie-break-adaptive-min-samples` (default 3) points exist, compute **p-percentile** (default **75**) via linear interpolation, then **clamp** to `[--tie-break-adaptive-clamp-min, --tie-break-adaptive-clamp-max]` (defaults **0.65–0.85**).
3. **Effective threshold** = `max(static tie_break_confidence_threshold, adaptive)`.

Promotion uses the **effective** threshold. Outputs include `tie_break_confidence_threshold_effective`, `adaptive_confidence_threshold`, and `tie_break_confidence_percentile_rank` (fraction of historical contested confidences strictly below this run’s confidence).

## Decision surface visualization (diagnostic)

Script: `tent_io/harness/tools/visualize_decision_surface.py`.

Builds a **synthetic grid** over external margin magnitude, metric agreement ratio, and tie-break streak using the same **floor → confidence → threshold** order as production. Optional NDJSON **history** raises the effective threshold when `--tie-break-adaptive-threshold` is set, and can **overlay** recent contested points on a PNG slice (requires matplotlib locally).

Example:

```bash
python3 tent_io/harness/tools/visualize_decision_surface.py \
  --streak-required 3 \
  --target-margin 0.03 \
  --confidence-threshold 0.75 \
  --output decision_surface.json
```

JSON always includes **`tie_break_blocking_reason_slice`** (dominant synthetic `tie_break_reason` over **(M, A)** at streak **`tie_break_blocking_reason_slice_streak`**, aligned with **`--png-streak`** / streak required). With **`--history`**, **`history_trajectory_contested`** lists time-ordered contested points (M, A, S) plus **`confidence_distance_to_threshold`**, **`confidence_velocity`**, **`normalized_confidence_velocity`** (Δdistance / (|previous distance| + ε)), **`confidence_acceleration`**, **`near_boundary_streak`**, **`blocking_reason_streak`** (consecutive runs with the same `tie_break_reason`), **`trajectory_blocking_reason`**, **`approach_delta_mas`**, and **`alignment_with_promotion_direction`** (cosine vs a fixed “all axes up” direction in scaled M–A–S space; heuristic). **`meta.trajectory_dynamics_summary`** includes **`stability_score`** [0, 1] (heuristic), **`dominant_blocking_reason`**, **`oscillation_amplitude_band`**, **`max_near_boundary_streak`**, and **`trajectory_dynamical_class`** (adds **`large_swing_instability`** when oscillation-like but **max(|distance|)** exceeds **`--oscillation-amplitude-band`**, default **0.2**). **`tie_break_boundary_crossings`**: sign flips of distance between consecutive trajectory points with numeric confidence. PNG: **`--png-include-blocking-reason`** adds a second panel; trajectory overlay uses **`--png-streak`**.

### Tie-break stability gate (optional, `compute_promotion_decision.py`)

When **`--tie-break-stability-gate`** is set, **`contested_external_override`** is allowed only if **`tie_break_stability_gate`** passes on contested history plus the current run (heuristic; not a proof of model stability). Optional flags: **`--tie-break-stability-require-upward-crossing`**, **`--tie-break-stability-max-abs-acceleration`**, **`--tie-break-stability-max-near-boundary-streak`**, **`--tie-break-stability-near-epsilon`**, **`--tie-break-stability-history-tail`**. Outputs: **`tie_break_stability_gate_enabled`**, **`tie_break_stability_gate_passed`**. Example failure codes: **`tie_break_stability_gate_high_acceleration`**, **`tie_break_stability_gate_near_boundary_dwell`**, **`tie_break_stability_gate_missing_upward_crossing`**.

### Effective confidence + hysteresis (optional, `compute_promotion_decision.py`)

- **Stability-weighted metric:** with **`--tie-break-use-effective-confidence`**, the arbitration metric becomes **`tie_break_effective_confidence = tie_break_confidence * tie_break_stability_score`**. Threshold defaults to the current tie-break threshold unless **`--tie-break-effective-confidence-threshold`** is set.
- **Hysteresis mode:** with **`--tie-break-hysteresis-enable`**, entry uses **high** threshold (`--tie-break-hysteresis-high`, default metric threshold), while retention uses **low** threshold (`--tie-break-hysteresis-low`, default high−0.05). The previous state comes from history field **`tie_break_hysteresis_above`**.
- **Optional upward-only entry:** **`--tie-break-hysteresis-upward-only`** requires an explicit upward crossing event before entering from below.
- Output fields include: **`tie_break_metric_used`**, **`tie_break_metric_value`**, **`tie_break_metric_threshold_effective`**, **`tie_break_effective_confidence`**, **`tie_break_stability_score`**, **`tie_break_hysteresis_enabled`**, **`tie_break_hysteresis_passed`**, **`tie_break_hysteresis_prev_above`**, **`tie_break_hysteresis_high`**, **`tie_break_hysteresis_low`**, **`tie_break_trajectory_dynamical_class`**.

**Mapping to informal language**

| Informal | Implementation |
|----------|------------------|
| promote (policy) | `aligned_ready_for_promotion` **and** downstream gates + optional advisory `promote_candidate` |
| hold | `aligned_pending_confirmation`, `aligned_but_margin_insufficient`, or advisory `observe` / `hold` |
| contested | `contested` |
| reject (hard fail) | Regression/readiness/trend **alarm** (separate scripts), baseline drift failure, or `promotion_allowed=false` with enforcement |

## Streak and hysteresis (defaults)

- **`promotion_alignment_required_runs`** (workflow input, default **2**): consecutive aligned runs required before `aligned_ready_for_promotion`.
- **`intelligence_advisory_required_streak`** (workflow input, default **2**): consecutive `promote_candidate` **base** states before advisory can surface `promote_candidate` (when enforcement is on).

**Contested runs** do not count as aligned; streak resets when alignment breaks.

## Weighted or dual-baseline policies

The codebase implements **slot agreement + margins + streaks** (conservative path). A weighted composite or dual baseline would be a **separate, explicit change** (new inputs + documented formula)—not implied by current scripts.

## CI summary: promotion proposal (advisory)

In `.github/workflows/tent-io-llt-expansion.yml`, the step summary may include **`## 🚀 Promotion Proposal`**. This is a **recommendation only**; it does not change baselines or override `promotion_allowed` / regression gates.

**Trigger (all required, as implemented in the workflow):**

- Readiness score (same advisory scalar as **Promotion Readiness Signal**) ≥ **0.80**
- Current run `tie_break_stability_score` ≥ **0.7**
- Short-window **consistency** (from rolling trend over `trend_window`) ≥ **0.7**

When triggered, the summary lists **`Candidate`** from `external_favored_slot` (`expand_s1` / `expand_s2`) when present; otherwise `unknown`.

**Artifact:** the workflow writes **`promotion_proposal.flag`** in the workspace root with `TRIGGERED` or `NOT_TRIGGERED` (also written when the promotion decision JSON is missing). Downstream steps or reusable workflows can read this file.

**PR history (two-run confirmation):** On **`pull_request`**, each run also appends one line (`TRIGGERED` or `NOT_TRIGGERED`) to **`promotion_proposal.history`**. The workflow restores a per-PR copy via **`actions/cache`** (`key: promo-proposal-pr-<number>`) so consecutive runs on the same PR can see prior lines. An advisory **PR comment** posts only when **`promotion_proposal.flag`** is `TRIGGERED` **and** the **suffix streak** of `TRIGGERED` lines at end-of-file is **≥ 2**: scan top-to-bottom, increment on `TRIGGERED`, reset to 0 on any other line; the value at EOF must be ≥ 2 (same idea as “two consecutive `TRIGGERED` lines at the tail,” with a single rule for edge cases like stray blank lines). **Note:** GitHub cache eviction and fork/permissions limits can reset or block this; the summary remains authoritative.

**PR comment (optional):** `.github/workflows/tent-io-llt-expansion.yml` posts an advisory comment when the two-run condition above **and** `github.event_name == 'pull_request'` are satisfied.

On PR runs, the workflow summary also includes **`## PR promotion confirmation (advisory)`** with a **Status** line: 🟢 **CONFIRMED (2/2)** or 🟡 **BUILDING (n/2)** (suffix streak clamped to the required length 2), or 🔴 **NOT TRIGGERED** without a fraction; plus suffix streak, this-run flag, and whether the PR comment gate passed—so the decision is visible without opening logs.

The workflow summary also surfaces instability in decision compression sections for visibility only:

- Under **`## 🚦 Promotion Readiness Signal`**, it emits an inline warning when instability is detected.
- Under **`## 🚀 Promotion Proposal`**, it mirrors the warning as advisory context.
- Detection is derived from `tie_break_trajectory_dynamical_class` in `{oscillating_boundary, large_swing_instability}` or `tie_break_stability_score < 0.4`.
- This warning is diagnostic-only and does **not** change readiness/proposal thresholds or policy gates.

**Triggers:** The workflow runs `expansion-sweep` on **`workflow_dispatch`** or **`pull_request`** (types `opened`, `synchronize`, `reopened`) with a **`paths`** filter on `tent_io/**` and this workflow file, so unrelated edits do not start the sweep. Other jobs (e.g. `auto-all-compare`) remain dispatch-only unless changed separately.

**Inputs on PRs:** The `inputs` context is only populated for `workflow_dispatch`. The job runs `tent_io/harness/scripts/resolve_workflow_dispatch_inputs.py` to write `INPUTS_*` environment variables from `github.event.inputs` when dispatch, otherwise from the same defaults as the workflow YAML (keep the script’s `DEFAULTS` in sync when adding or changing inputs).

**Fork PRs:** Comment posting may require appropriate token permissions and repository settings; advisory behavior is unchanged if the comment step cannot run.

## PR labels (optional visibility)

When **`expansion-sweep`** runs on a **`pull_request`** and the PR confirmation step succeeds, **`Apply promotion labels (PR)`** updates issue labels (advisory; does not change baselines or merge):

| Condition | Action |
|-----------|--------|
| `confirmed` is true (suffix streak ≥ 2 and this run `TRIGGERED`) | Add **`promotion:ready`**, remove **`promotion:building`** and **`promotion:unstable`** |
| Else if `promotion_proposal.flag` is **`TRIGGERED`** | Add **`promotion:building`**, remove **`promotion:ready`** and **`promotion:unstable`** |
| Else if unstable (`tie_break_trajectory_dynamical_class` is `oscillating_boundary`/`large_swing_instability`, or `tie_break_stability_score < 0.4`) | Add **`promotion:unstable`**, remove **`promotion:ready`** and **`promotion:building`** |
| Else | Remove **`promotion:ready`**, **`promotion:building`**, and **`promotion:unstable`** |

**Repo setup:** Create **`promotion:ready`**, **`promotion:building`**, and **`promotion:unstable`** in the repository (or org) label settings so `addLabels` succeeds. If a label is missing, the step may fail until the label exists.

## Post-promotion tracking (advisory)

`tent-io-llt-expansion.yml` step summary includes **`## 📉 Post-Promotion Tracking`** as a read-only check of what happened after the latest promotable decision point in history (`promotion_allowed=true` with `decision_state` in `aligned_ready_for_promotion` or `contested_external_override`).

Current advisory window is the next **5** runs after that promotion point. Reported fields:

- Promoted profile and relative run index
- Retained dominance rate (`external_favored_slot == promoted_profile`)
- Win stability (flip-aware)
- Average pressure (`tie_break_confidence - tie_break_confidence_threshold_effective`)
- Confidence delta versus the promotion run
- Current favored slot
- Status: `🟢 holding`, `🟡 mixed`, or `🔴 degrading`

This section is advisory-only and does **not** change promotion gates, labels, or baseline mutation behavior.

## Related

- `LLT_GOVERNANCE_AND_EVAL_STACK_WHITEPAPER.md` — artifact paths.
- `INTELLIGENCE_TUNING.md` — enforcement flags and floors.
- `compute_promotion_decision.py` — source of `internal_slot`, `external_favored_slot`, `promotion_blocked_reason`.
