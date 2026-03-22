#!/usr/bin/env python3
"""Compute ML/AI/AGI-oriented intelligence scoring from expansion artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def metric_from_profile(profile_payload: dict[str, Any]) -> dict[str, float | None]:
    metrics = profile_payload.get("metrics")
    if not isinstance(metrics, dict):
        return {
            "mmlu_pro_acc": None,
            "gpqa_acc": None,
            "long_context_acc": None,
            "consistency_score": None,
        }
    return {
        "mmlu_pro_acc": as_float(metrics.get("mmlu_pro_acc")),
        "gpqa_acc": as_float(metrics.get("gpqa_acc")),
        "long_context_acc": as_float(metrics.get("long_context_acc")),
        "consistency_score": as_float(metrics.get("consistency_score")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute intelligence scoring and logic-chain quality metrics")
    parser.add_argument("--sweep-summary", type=Path, required=True)
    parser.add_argument("--external-compare", type=Path, required=False, default=None)
    parser.add_argument("--promotion-decision", type=Path, required=False, default=None)
    parser.add_argument("--promotion-trend", type=Path, required=False, default=None)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    args = parser.parse_args()

    sweep = load_json(args.sweep_summary)
    external = load_json(args.external_compare) if args.external_compare else {}
    decision = load_json(args.promotion_decision) if args.promotion_decision else {}
    trend = load_json(args.promotion_trend) if args.promotion_trend else {}

    best = sweep.get("best_profile") if isinstance(sweep.get("best_profile"), dict) else {}
    internal_profile = best.get("profile") if isinstance(best.get("profile"), str) else None
    final_acc = as_float(best.get("final_test_acc")) or 0.0
    mmlu_acc = as_float(best.get("final_mmlu_test_acc")) or 0.0
    conv_acc = as_float(best.get("final_conversational_logic_test_acc")) or 0.0
    replay_final = as_float(best.get("replay_test_acc"))
    replay_mmlu = as_float(best.get("replay_mmlu_test_acc"))
    replay_conv = as_float(best.get("replay_conversational_logic_test_acc"))
    drift = abs(as_float(best.get("train_eval_drift")) or 0.0)

    replay_gap = 0.0
    gap_count = 0
    for a, b in ((final_acc, replay_final), (mmlu_acc, replay_mmlu), (conv_acc, replay_conv)):
        if b is not None:
            replay_gap += abs(a - float(b))
            gap_count += 1
    replay_gap = replay_gap / gap_count if gap_count else 0.0
    replay_consistency = clamp01(1.0 - replay_gap)

    # Logic-chain quality focuses on conversational logic, MMLU reasoning support,
    # and replay consistency under deterministic constraints.
    logic_chain_score = clamp01(0.50 * conv_acc + 0.30 * mmlu_acc + 0.20 * replay_consistency)

    # Internal model capability score.
    ml_score = clamp01(0.45 * mmlu_acc + 0.30 * final_acc + 0.20 * conv_acc + 0.05 * replay_consistency)

    ext_favored = external.get("favored_profile") if isinstance(external.get("favored_profile"), str) else None
    winner_votes = external.get("winner_votes") if isinstance(external.get("winner_votes"), dict) else {}
    s1_payload = external.get("expand_s1") if isinstance(external.get("expand_s1"), dict) else {}
    s2_payload = external.get("expand_s2") if isinstance(external.get("expand_s2"), dict) else {}
    s1_metrics = metric_from_profile(s1_payload)
    s2_metrics = metric_from_profile(s2_payload)

    external_profile_metrics = {}
    if internal_profile == "expand_s1":
        external_profile_metrics = s1_metrics
    elif internal_profile == "expand_s2":
        external_profile_metrics = s2_metrics
    else:
        external_profile_metrics = {
            "mmlu_pro_acc": None,
            "gpqa_acc": None,
            "long_context_acc": None,
            "consistency_score": None,
        }

    ext_mmlu_pro = external_profile_metrics.get("mmlu_pro_acc")
    ext_gpqa = external_profile_metrics.get("gpqa_acc")
    ext_long = external_profile_metrics.get("long_context_acc")
    ext_consistency = external_profile_metrics.get("consistency_score")
    ext_values = [v for v in (ext_mmlu_pro, ext_gpqa, ext_long, ext_consistency) if isinstance(v, float)]
    external_strength = float(sum(ext_values) / len(ext_values)) if ext_values else 0.0

    internal_external_alignment = 0.5
    if isinstance(ext_favored, str) and isinstance(internal_profile, str):
        internal_external_alignment = 1.0 if ext_favored == internal_profile else 0.0

    ai_score = clamp01(0.55 * ml_score + 0.35 * external_strength + 0.10 * internal_external_alignment)

    decision_state = decision.get("decision_state") if isinstance(decision.get("decision_state"), str) else "insufficient_signal"
    promotion_allowed = decision.get("promotion_allowed") is True
    contested_ratio_recent = as_float(trend.get("contested_ratio_recent")) if isinstance(trend, dict) else None
    contested_ratio_recent = float(contested_ratio_recent) if contested_ratio_recent is not None else 1.0

    governance_strength = 0.0
    if decision_state == "aligned_ready_for_promotion":
        governance_strength = 1.0
    elif decision_state in {"aligned_pending_confirmation", "aligned_but_margin_insufficient"}:
        governance_strength = 0.7
    elif decision_state == "contested":
        governance_strength = 0.3
    else:
        governance_strength = 0.2
    governance_strength = clamp01(0.75 * governance_strength + 0.25 * (1.0 - contested_ratio_recent))

    determinism_strength = clamp01(1.0 - min(1.0, drift * 1000000.0))

    agi_readiness = clamp01(
        0.35 * ai_score
        + 0.25 * logic_chain_score
        + 0.25 * governance_strength
        + 0.15 * determinism_strength
    )

    out = {
        "status": "ok",
        "internal_profile": internal_profile,
        "decision_state": decision_state,
        "promotion_allowed": promotion_allowed,
        "scores": {
            "ml_intelligence_score": ml_score,
            "logic_chain_score": logic_chain_score,
            "ai_intelligence_score": ai_score,
            "agi_readiness_score": agi_readiness,
        },
        "components": {
            "internal": {
                "final_test_acc": final_acc,
                "mmlu_test_acc": mmlu_acc,
                "conversational_logic_test_acc": conv_acc,
                "replay_consistency": replay_consistency,
                "train_eval_drift_abs": drift,
            },
            "external": {
                "favored_profile": ext_favored,
                "winner_votes": winner_votes,
                "internal_profile_metrics": external_profile_metrics,
                "internal_external_alignment": internal_external_alignment,
                "external_strength": external_strength,
            },
            "governance": {
                "decision_state": decision_state,
                "promotion_allowed": promotion_allowed,
                "contested_ratio_recent": contested_ratio_recent,
                "governance_strength": governance_strength,
                "determinism_strength": determinism_strength,
            },
        },
        "inputs": {
            "sweep_summary": str(args.sweep_summary),
            "external_compare": str(args.external_compare) if args.external_compare else None,
            "promotion_decision": str(args.promotion_decision) if args.promotion_decision else None,
            "promotion_trend": str(args.promotion_trend) if args.promotion_trend else None,
        },
    }

    lines = [
        "# Intelligence Scoring",
        "",
        f"- internal_profile: `{internal_profile}`",
        f"- decision_state: `{decision_state}`",
        f"- promotion_allowed: `{promotion_allowed}`",
        f"- ml_intelligence_score: `{ml_score}`",
        f"- logic_chain_score: `{logic_chain_score}`",
        f"- ai_intelligence_score: `{ai_score}`",
        f"- agi_readiness_score: `{agi_readiness}`",
        f"- external_favored_profile: `{ext_favored}`",
        f"- contested_ratio_recent: `{contested_ratio_recent}`",
    ]

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out_json": str(args.out_json), "out_md": str(args.out_md)}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
