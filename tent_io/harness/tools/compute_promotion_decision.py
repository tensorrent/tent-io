#!/usr/bin/env python3
"""
Compute promotion decision state from internal sweep summary + external compare.

See ``docs/PROMOTION_POLICY_GOVERNANCE.md`` and ``promotion_decision_logic.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from promotion_decision_logic import (  # noqa: E402
    VALID_EXPAND_SLOTS,
    adaptive_effective_threshold,
    agreement_ratio_for_favor,
    alignment_streak_after_run,
    confidence_percentile_rank,
    contested_tie_break_confidences_from_history_lines,
    drift_near_zero,
    external_aggregate_margin,
    external_tie_break_streak,
    tie_break_confidence,
    tie_break_momentum,
)
from trajectory_dynamics import (  # noqa: E402
    add_approach_vectors,
    augment_trajectory_dynamics,
    boundary_crossings_from_trajectory,
    contested_trajectory_plus_current,
    enrich_trajectory_with_threshold_distance,
    tie_break_stability_gate,
    trajectory_dynamics_summary_dict,
)


def margin_consistent_with_favor(favored: str, margin_signed: float | None, eps: float = 1e-9) -> bool:
    if margin_signed is None:
        return False
    if favored == "expand_s1":
        return margin_signed > eps
    if favored == "expand_s2":
        return margin_signed < -eps
    return False


def _last_history_row(history_lines: list[str]) -> dict | None:
    if not history_lines:
        return None
    try:
        row = json.loads(history_lines[-1].strip())
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    return row if isinstance(row, dict) else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute promotion decision state.")
    parser.add_argument("--internal-summary", required=True, help="Path to internal sweep summary JSON")
    parser.add_argument("--external-compare", required=True, help="Path to external comparison JSON")
    parser.add_argument("--out", required=True, help="Output decision JSON path")
    parser.add_argument("--history-out", required=True, help="Path to append NDJSON history")
    parser.add_argument("--alignment-required-runs", type=int, default=2)
    parser.add_argument("--min-internal-margin", type=float, default=0.005)
    parser.add_argument("--min-external-vote-margin", type=int, default=1)
    parser.add_argument(
        "--contested-external-tie-break",
        action="store_true",
        help="If set, allow optional promotion path when contested (external margin + streak).",
    )
    parser.add_argument(
        "--external-margin-threshold",
        type=float,
        default=0.02,
        help="Deprecated alias: use --tie-break-margin-floor for momentum floor.",
    )
    parser.add_argument("--external-tie-break-streak-required", type=int, default=3)
    parser.add_argument("--tie-break-margin-floor", type=float, default=0.01)
    parser.add_argument("--tie-break-agreement-floor", type=float, default=0.6)
    parser.add_argument("--tie-break-confidence-threshold", type=float, default=0.75)
    parser.add_argument("--tie-break-target-margin", type=float, default=0.03)
    parser.add_argument("--tie-break-drift-tol", type=float, default=1e-6)
    parser.add_argument(
        "--tie-break-relax-drift-check",
        action="store_true",
        help="If set, drift stability term D=1.0 in tie-break confidence.",
    )
    parser.add_argument(
        "--tie-break-adaptive-threshold",
        action="store_true",
        help="Raise tie-break bar using p-percentile of recent contested tie_break_confidence history.",
    )
    parser.add_argument("--tie-break-adaptive-window", type=int, default=20)
    parser.add_argument("--tie-break-adaptive-percentile", type=float, default=75.0)
    parser.add_argument("--tie-break-adaptive-clamp-min", type=float, default=0.65)
    parser.add_argument("--tie-break-adaptive-clamp-max", type=float, default=0.85)
    parser.add_argument("--tie-break-adaptive-min-samples", type=int, default=3)
    parser.add_argument(
        "--tie-break-stability-gate",
        action="store_true",
        help="Extra trajectory checks before contested_external_override (spike / dwell / optional upward crossing).",
    )
    parser.add_argument(
        "--tie-break-stability-require-upward-crossing",
        action="store_true",
        help="Require prior contested run below effective threshold and current at/above.",
    )
    parser.add_argument(
        "--tie-break-stability-max-abs-acceleration",
        type=float,
        default=None,
        help="Block override if last |confidence_acceleration| exceeds this (None = skip).",
    )
    parser.add_argument(
        "--tie-break-stability-max-near-boundary-streak",
        type=int,
        default=None,
        help="Block override if last near_boundary_streak >= this (None = skip).",
    )
    parser.add_argument("--tie-break-stability-near-epsilon", type=float, default=0.05)
    parser.add_argument(
        "--tie-break-stability-history-tail",
        type=int,
        default=64,
        help="Max prior contested M–A–S points to include when evaluating the gate.",
    )
    parser.add_argument(
        "--tie-break-use-effective-confidence",
        action="store_true",
        help="Use confidence * stability_score as tie-break metric (diagnostic scalar).",
    )
    parser.add_argument(
        "--tie-break-effective-confidence-threshold",
        type=float,
        default=None,
        help="Threshold for effective confidence (defaults to confidence threshold/effective threshold).",
    )
    parser.add_argument(
        "--tie-break-hysteresis-enable",
        action="store_true",
        help="Enable hysteresis on tie-break metric: promote at high threshold, retain via lower threshold.",
    )
    parser.add_argument("--tie-break-hysteresis-high", type=float, default=None)
    parser.add_argument("--tie-break-hysteresis-low", type=float, default=None)
    parser.add_argument(
        "--tie-break-hysteresis-upward-only",
        action="store_true",
        help="When entering promoted state (from below), require an upward crossing event.",
    )
    parser.add_argument(
        "--tie-break-oscillation-amplitude-band",
        type=float,
        default=0.2,
        help="Classification band for oscillating_boundary vs large_swing_instability.",
    )

    args = parser.parse_args()

    try:
        with open(args.internal_summary, encoding="utf-8") as f:
            int_data = json.load(f)
        with open(args.external_compare, encoding="utf-8") as f:
            ext_data = json.load(f)
    except OSError as e:
        print(f"Error loading inputs: {e!s}", file=sys.stderr)
        sys.exit(1)

    int_bp = int_data.get("best_profile", {})
    if not isinstance(int_bp, dict):
        int_bp = {}
    internal_slot = int_bp.get("profile")
    if not isinstance(internal_slot, str):
        internal_slot = None

    int_margin = float(int_bp.get("margin") or 0.0)

    ext_favored_slot = ext_data.get("favored_profile")
    if not isinstance(ext_favored_slot, str):
        ext_favored_slot = None

    s1_name = ext_data.get("expand_s1", {}).get("profile") if isinstance(ext_data.get("expand_s1"), dict) else None
    s2_name = ext_data.get("expand_s2", {}).get("profile") if isinstance(ext_data.get("expand_s2"), dict) else None

    if ext_favored_slot == "expand_s1":
        external_winner_name = s1_name if isinstance(s1_name, str) else None
    elif ext_favored_slot == "expand_s2":
        external_winner_name = s2_name if isinstance(s2_name, str) else None
    else:
        external_winner_name = None

    ext_vote_margin = 0
    wv = ext_data.get("winner_votes") if isinstance(ext_data.get("winner_votes"), dict) else {}
    if ext_favored_slot and ext_favored_slot in wv:
        ext_vote_margin = int(wv.get(ext_favored_slot, 0)) - int(wv.get("tie_or_missing", 0))

    _s1a, _s2a, margin_signed = external_aggregate_margin(ext_data)
    margin_abs = abs(margin_signed) if margin_signed is not None else None

    agreement_ratio: float | None = None
    if ext_favored_slot in VALID_EXPAND_SLOTS:
        agreement_ratio = agreement_ratio_for_favor(ext_data, ext_favored_slot)

    margin_floor = args.tie_break_margin_floor

    aligned = False
    contested = False
    promotion_blocked_reason: str | None = None
    alignment_basis = "none"

    if internal_slot and ext_favored_slot in VALID_EXPAND_SLOTS:
        alignment_basis = "slot"
        if internal_slot in VALID_EXPAND_SLOTS:
            if internal_slot != ext_favored_slot:
                contested = True
                promotion_blocked_reason = "internal_external_slot_mismatch"
            else:
                aligned = True
        else:
            if external_winner_name and internal_slot == external_winner_name:
                aligned = True
                alignment_basis = "name_fallback"
            elif external_winner_name:
                contested = True
                promotion_blocked_reason = "internal_external_name_mismatch_noncanonical_internal_slot"
            else:
                contested = True
                promotion_blocked_reason = "missing_external_profile_name_for_fallback"
    elif internal_slot and ext_favored_slot == "tie_or_missing":
        alignment_basis = "tie_or_missing"
        contested = False
        aligned = False
        promotion_blocked_reason = "external_favor_unresolved"
    elif internal_slot and ext_favored_slot and ext_favored_slot not in VALID_EXPAND_SLOTS and ext_favored_slot != "tie_or_missing":
        contested = True
        promotion_blocked_reason = "external_favored_profile_unexpected"

    history_lines: list[str] = []
    if os.path.exists(args.history_out):
        try:
            with open(args.history_out, encoding="utf-8") as f:
                history_lines = f.readlines()
        except OSError:
            history_lines = []

    streak = alignment_streak_after_run(history_lines, aligned)
    tb_streak = external_tie_break_streak(
        history_lines,
        contested=contested,
        enabled=args.contested_external_tie_break,
        margin_abs=margin_abs,
        margin_floor=margin_floor,
        ext_favored_slot=ext_favored_slot,
    )
    tb_momentum = tie_break_momentum(contested, margin_abs, margin_floor)

    drift_ok = drift_near_zero(int_bp) if not args.tie_break_relax_drift_check else True

    if not internal_slot:
        state = "insufficient_signal"
        if not promotion_blocked_reason:
            promotion_blocked_reason = "missing_internal_profile"
    elif not ext_favored_slot or ext_favored_slot == "tie_or_missing":
        state = "insufficient_signal"
        if not promotion_blocked_reason:
            promotion_blocked_reason = "external_favor_unresolved"
    elif contested:
        state = "contested"
    elif not aligned:
        state = "insufficient_signal"
        if not promotion_blocked_reason:
            promotion_blocked_reason = "not_aligned"
    else:
        meets_int = int_margin >= args.min_internal_margin
        meets_ext = ext_vote_margin >= args.min_external_vote_margin
        if streak < args.alignment_required_runs:
            state = "aligned_pending_confirmation"
        elif not (meets_int and meets_ext):
            state = "aligned_but_margin_insufficient"
        else:
            state = "aligned_ready_for_promotion"

    tie_break_applied = False
    tie_break_reason: str | None = None
    tie_break_confidence_val: float | None = None
    confidence_components: dict[str, float] = {}
    adaptive_confidence_threshold: float | None = None
    tie_break_confidence_threshold_effective: float | None = None
    tie_break_confidence_percentile_rank: float | None = None
    tie_break_stability_gate_passed: bool | None = None
    tie_break_stability_score: float | None = None
    tie_break_effective_confidence: float | None = None
    tie_break_metric_used: str = "confidence"
    tie_break_metric_value: float | None = None
    tie_break_metric_threshold_effective: float | None = None
    tie_break_hysteresis_enabled = bool(args.tie_break_hysteresis_enable)
    tie_break_hysteresis_passed: bool | None = None
    tie_break_hysteresis_prev_above: bool | None = None
    tie_break_hysteresis_high: float | None = None
    tie_break_hysteresis_low: float | None = None
    tie_break_trajectory_class: str | None = None

    hist_conf_adaptive = contested_tie_break_confidences_from_history_lines(
        history_lines,
        max_tail=args.tie_break_adaptive_window,
    )
    if args.tie_break_adaptive_threshold:
        tie_break_confidence_threshold_effective, adaptive_confidence_threshold = adaptive_effective_threshold(
            args.tie_break_confidence_threshold,
            historical_confidences=hist_conf_adaptive,
            percentile=args.tie_break_adaptive_percentile,
            clamp_min=args.tie_break_adaptive_clamp_min,
            clamp_max=args.tie_break_adaptive_clamp_max,
            min_samples=args.tie_break_adaptive_min_samples,
        )
    else:
        tie_break_confidence_threshold_effective = args.tie_break_confidence_threshold

    if args.contested_external_tie_break and state == "contested" and ext_favored_slot in VALID_EXPAND_SLOTS:
        if agreement_ratio is None:
            tie_break_reason = "no_nonzero_metric_deltas"
        elif agreement_ratio < args.tie_break_agreement_floor:
            tie_break_reason = "low_metric_agreement"
        elif margin_abs is None or margin_abs < args.tie_break_margin_floor:
            tie_break_reason = "margin_too_small"
        elif not margin_consistent_with_favor(ext_favored_slot, margin_signed):
            tie_break_reason = "aggregate_margin_sign_mismatch"
        else:
            conf, confidence_components = tie_break_confidence(
                margin_abs=margin_abs,
                tb_streak=tb_streak,
                streak_required=args.external_tie_break_streak_required,
                agreement_ratio=agreement_ratio,
                best_profile=int_bp,
                relax_drift=args.tie_break_relax_drift_check,
                target_margin=args.tie_break_target_margin,
                drift_tol=args.tie_break_drift_tol,
            )
            tie_break_confidence_val = conf
            tie_break_confidence_percentile_rank = confidence_percentile_rank(conf, hist_conf_adaptive)
            eff_thr = tie_break_confidence_threshold_effective if tie_break_confidence_threshold_effective is not None else args.tie_break_confidence_threshold
            trj = contested_trajectory_plus_current(
                history_lines,
                current_row={
                    "external_margin_abs": margin_abs,
                    "external_metric_agreement_ratio": float(agreement_ratio),
                    "external_tie_break_streak": tb_streak,
                    "tie_break_confidence": conf,
                    "tie_break_confidence_threshold_effective": eff_thr,
                    "tie_break_reason": "tie_break_confidence_threshold_met",
                    "decision_state": "contested",
                },
                history_tail_max_points=int(args.tie_break_stability_history_tail),
            )
            trj = enrich_trajectory_with_threshold_distance(trj, threshold_fallback=float(eff_thr))
            crossings = boundary_crossings_from_trajectory(trj)
            trj = augment_trajectory_dynamics(trj, near_boundary_epsilon=float(args.tie_break_stability_near_epsilon))
            trj = add_approach_vectors(trj, streak_scale=float(max(1, args.external_tie_break_streak_required)))
            dyn = trajectory_dynamics_summary_dict(
                trj,
                near_boundary_epsilon=float(args.tie_break_stability_near_epsilon),
                boundary_crossings=crossings,
                oscillation_amplitude_band=float(args.tie_break_oscillation_amplitude_band),
            )
            tie_break_stability_score = dyn.get("stability_score") if isinstance(dyn.get("stability_score"), (int, float)) else None
            tie_break_trajectory_class = dyn.get("trajectory_dynamical_class") if isinstance(dyn.get("trajectory_dynamical_class"), str) else None
            if tie_break_stability_score is not None:
                tie_break_effective_confidence = conf * tie_break_stability_score
            metric = tie_break_effective_confidence if (args.tie_break_use_effective_confidence and tie_break_effective_confidence is not None) else conf
            tie_break_metric_used = "effective_confidence" if args.tie_break_use_effective_confidence else "confidence"
            tie_break_metric_value = metric
            metric_thr = (
                float(args.tie_break_effective_confidence_threshold)
                if args.tie_break_effective_confidence_threshold is not None
                else float(eff_thr)
            )
            tie_break_metric_threshold_effective = metric_thr

            if args.tie_break_hysteresis_enable:
                tie_break_hysteresis_high = (
                    float(args.tie_break_hysteresis_high)
                    if args.tie_break_hysteresis_high is not None
                    else metric_thr
                )
                tie_break_hysteresis_low = (
                    float(args.tie_break_hysteresis_low)
                    if args.tie_break_hysteresis_low is not None
                    else max(0.0, tie_break_hysteresis_high - 0.05)
                )
                last_row = _last_history_row(history_lines)
                if isinstance(last_row, dict):
                    prev_above_raw = last_row.get("tie_break_hysteresis_above")
                    tie_break_hysteresis_prev_above = bool(prev_above_raw) if isinstance(prev_above_raw, bool) else None
                if tie_break_hysteresis_prev_above:
                    tie_break_hysteresis_passed = metric >= tie_break_hysteresis_low
                else:
                    tie_break_hysteresis_passed = metric >= tie_break_hysteresis_high
                metric_pass = bool(tie_break_hysteresis_passed)
                if (
                    metric_pass
                    and args.tie_break_hysteresis_upward_only
                    and not tie_break_hysteresis_prev_above
                    and not crossings
                ):
                    metric_pass = False
                    tie_break_hysteresis_passed = False
                    tie_break_reason = "tie_break_hysteresis_requires_upward_crossing"
            else:
                metric_pass = metric >= metric_thr

            if metric_pass:
                stability_ok = True
                stability_reason: str | None = None
                if args.tie_break_stability_gate:
                    ok, sr = tie_break_stability_gate(
                        history_lines,
                        current_row={
                            "external_margin_abs": margin_abs,
                            "external_metric_agreement_ratio": float(agreement_ratio),
                            "external_tie_break_streak": tb_streak,
                            "tie_break_confidence": conf,
                            "tie_break_confidence_threshold_effective": eff_thr,
                            "tie_break_reason": "tie_break_confidence_threshold_met",
                            "decision_state": "contested",
                        },
                        threshold_fallback=float(eff_thr),
                        near_boundary_epsilon=float(args.tie_break_stability_near_epsilon),
                        require_upward_crossing=bool(args.tie_break_stability_require_upward_crossing),
                        max_abs_acceleration=args.tie_break_stability_max_abs_acceleration,
                        max_near_boundary_streak=args.tie_break_stability_max_near_boundary_streak,
                        history_tail_max_points=int(args.tie_break_stability_history_tail),
                    )
                    stability_ok = ok
                    stability_reason = sr
                    tie_break_stability_gate_passed = ok
                if stability_ok:
                    state = "contested_external_override"
                    tie_break_applied = True
                    tie_break_reason = (
                        "tie_break_effective_confidence_threshold_met"
                        if tie_break_metric_used == "effective_confidence"
                        else "tie_break_confidence_threshold_met"
                    )
                else:
                    state = "contested"
                    tie_break_applied = False
                    tie_break_reason = stability_reason or "tie_break_stability_gate_failed"
            else:
                if tie_break_reason is None:
                    tie_break_reason = (
                        "tie_break_effective_confidence_below_effective_threshold"
                        if tie_break_metric_used == "effective_confidence"
                        else "tie_break_confidence_below_effective_threshold"
                    )

    allowed = state in ("aligned_ready_for_promotion", "contested_external_override")

    output: dict = {
        "status": "ok",
        "decision_state": state,
        "promotion_allowed": allowed,
        "internal_winner": internal_slot,
        "external_winner": external_winner_name,
        "internal_slot": internal_slot,
        "external_favored_slot": ext_favored_slot,
        "alignment_basis": alignment_basis,
        "aligned": aligned,
        "contested": contested,
        "promotion_blocked_reason": promotion_blocked_reason,
        "alignment_required_runs": args.alignment_required_runs,
        "aligned_streak": streak,
        "internal_margin": int_margin,
        "min_internal_margin": args.min_internal_margin,
        "external_vote_margin": ext_vote_margin,
        "min_external_vote_margin": args.min_external_vote_margin,
        "meets_internal_margin": int_margin >= args.min_internal_margin,
        "meets_external_margin": ext_vote_margin >= args.min_external_vote_margin,
        "external_margin_signed": margin_signed,
        "external_margin_abs": margin_abs,
        "external_aggregate_s1": _s1a,
        "external_aggregate_s2": _s2a,
        "external_metric_agreement_ratio": agreement_ratio,
        "tie_break_momentum": tb_momentum,
        "external_tie_break_streak": tb_streak,
        "external_tie_break_streak_required": args.external_tie_break_streak_required,
        "contested_external_tie_break_enabled": args.contested_external_tie_break,
        "tie_break_applied": tie_break_applied,
        "tie_break_reason": tie_break_reason,
        "tie_break_confidence": tie_break_confidence_val,
        "tie_break_confidence_threshold": args.tie_break_confidence_threshold,
        "tie_break_confidence_threshold_effective": tie_break_confidence_threshold_effective,
        "adaptive_confidence_threshold": adaptive_confidence_threshold,
        "tie_break_adaptive_enabled": args.tie_break_adaptive_threshold,
        "tie_break_confidence_percentile_rank": tie_break_confidence_percentile_rank,
        "tie_break_stability_score": tie_break_stability_score,
        "tie_break_effective_confidence": tie_break_effective_confidence,
        "tie_break_metric_used": tie_break_metric_used,
        "tie_break_metric_value": tie_break_metric_value,
        "tie_break_metric_threshold_effective": tie_break_metric_threshold_effective,
        "tie_break_hysteresis_enabled": tie_break_hysteresis_enabled,
        "tie_break_hysteresis_passed": tie_break_hysteresis_passed,
        "tie_break_hysteresis_prev_above": tie_break_hysteresis_prev_above,
        "tie_break_hysteresis_high": tie_break_hysteresis_high,
        "tie_break_hysteresis_low": tie_break_hysteresis_low,
        "tie_break_trajectory_dynamical_class": tie_break_trajectory_class,
        "tie_break_confidence_components": confidence_components,
        "tie_break_agreement_floor": args.tie_break_agreement_floor,
        "tie_break_margin_floor": args.tie_break_margin_floor,
        "tie_break_target_margin": args.tie_break_target_margin,
        "tie_break_require_zero_drift": not args.tie_break_relax_drift_check,
        "tie_break_drift_ok": drift_ok,
        "tie_break_stability_gate_enabled": args.tie_break_stability_gate,
        "tie_break_stability_gate_passed": tie_break_stability_gate_passed,
        "internal_summary": args.internal_summary,
        "external_compare": args.external_compare,
        "history_path": args.history_out,
    }

    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=True)
    except OSError as e:
        print(f"Error writing decision: {e!s}", file=sys.stderr)
        sys.exit(1)

    history_row = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decision_state": state,
        "promotion_allowed": allowed,
        "internal_winner": internal_slot,
        "external_winner": external_winner_name,
        "internal_slot": internal_slot,
        "external_favored_slot": ext_favored_slot,
        "aligned": aligned,
        "contested": contested,
        "promotion_blocked_reason": promotion_blocked_reason,
        "aligned_streak": streak,
        "alignment_required_runs": args.alignment_required_runs,
        "internal_margin": int_margin,
        "external_vote_margin": ext_vote_margin,
        "meets_internal_margin": int_margin >= args.min_internal_margin,
        "meets_external_margin": ext_vote_margin >= args.min_external_vote_margin,
        "external_margin_signed": margin_signed,
        "external_margin_abs": margin_abs,
        "external_aggregate_s1": _s1a,
        "external_aggregate_s2": _s2a,
        "external_metric_agreement_ratio": agreement_ratio,
        "tie_break_momentum": tb_momentum,
        "external_tie_break_streak": tb_streak,
        "tie_break_applied": tie_break_applied,
        "tie_break_confidence": tie_break_confidence_val,
        "tie_break_confidence_threshold_effective": tie_break_confidence_threshold_effective,
        "adaptive_confidence_threshold": adaptive_confidence_threshold,
        "tie_break_confidence_percentile_rank": tie_break_confidence_percentile_rank,
        "tie_break_stability_score": tie_break_stability_score,
        "tie_break_effective_confidence": tie_break_effective_confidence,
        "tie_break_metric_used": tie_break_metric_used,
        "tie_break_metric_value": tie_break_metric_value,
        "tie_break_metric_threshold_effective": tie_break_metric_threshold_effective,
        "tie_break_hysteresis_enabled": tie_break_hysteresis_enabled,
        "tie_break_hysteresis_passed": tie_break_hysteresis_passed,
        "tie_break_hysteresis_prev_above": tie_break_hysteresis_prev_above,
        "tie_break_hysteresis_high": tie_break_hysteresis_high,
        "tie_break_hysteresis_low": tie_break_hysteresis_low,
        "tie_break_hysteresis_above": (tie_break_hysteresis_passed if tie_break_hysteresis_enabled else None),
        "tie_break_trajectory_dynamical_class": tie_break_trajectory_class,
        "tie_break_confidence_components": confidence_components,
        "tie_break_stability_gate_enabled": args.tie_break_stability_gate,
        "tie_break_stability_gate_passed": tie_break_stability_gate_passed,
    }

    try:
        with open(args.history_out, "a", encoding="utf-8") as f:
            f.write(json.dumps(history_row, ensure_ascii=True) + "\n")
    except OSError as e:
        print(f"Warning: history write failed: {e!s}", file=sys.stderr)

    print(json.dumps(output, indent=2, ensure_ascii=True))
    sys.exit(0)


if __name__ == "__main__":
    main()
