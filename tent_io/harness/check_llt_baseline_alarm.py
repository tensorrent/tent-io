#!/usr/bin/env python3
"""Fail-closed baseline alarm checks for LLT expansion sweep outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing JSON file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON payload must be an object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Check LLT baseline drift alarms from expansion summary")
    parser.add_argument(
        "--summary",
        type=Path,
        default=REPO_ROOT / "tent_io" / "harness" / "reports" / "expansion" / "llt_expansion_sweep.current.json",
        help="Expansion sweep summary JSON path.",
    )
    parser.add_argument("--expected-profile", default="expand_s2", help="Expected best-profile name.")
    parser.add_argument(
        "--max-train-eval-drift",
        type=float,
        default=0.0,
        help="Fail when best_profile.train_eval_drift exceeds this value.",
    )
    parser.add_argument(
        "--require-train-gate-pass",
        action="store_true",
        help="Require best_profile.train_gate_passes is true.",
    )
    parser.add_argument(
        "--require-replay-gate-pass",
        action="store_true",
        help="Require best_profile.replay_gate_passes is true.",
    )
    parser.add_argument(
        "--require-drift-gate-pass",
        action="store_true",
        help="Require best_profile.drift_passes is true.",
    )
    parser.add_argument("--min-train-mmlu", type=float, default=-1.0, help="Expected minimum train MMLU split threshold.")
    parser.add_argument(
        "--min-train-conversational",
        type=float,
        default=-1.0,
        help="Expected minimum train conversational split threshold.",
    )
    parser.add_argument("--min-eval-mmlu", type=float, default=-1.0, help="Expected minimum eval MMLU split threshold.")
    parser.add_argument(
        "--min-eval-conversational",
        type=float,
        default=-1.0,
        help="Expected minimum eval conversational split threshold.",
    )
    args = parser.parse_args()

    if args.max_train_eval_drift < 0:
        raise SystemExit("--max-train-eval-drift must be >= 0")

    payload = load_json(args.summary)
    best = payload.get("best_profile")
    if not isinstance(best, dict):
        raise SystemExit("Missing best_profile in summary.")

    split_gates = payload.get("split_gates")
    if not isinstance(split_gates, dict):
        raise SystemExit("Missing split_gates in summary.")

    alarms: list[str] = []
    best_profile = best.get("profile")
    if best_profile != args.expected_profile:
        alarms.append(f"best_profile changed: expected={args.expected_profile} actual={best_profile}")

    drift = as_float(best.get("train_eval_drift"))
    if drift is None:
        alarms.append("best_profile.train_eval_drift missing/non-numeric")
    elif drift > args.max_train_eval_drift:
        alarms.append(f"train_eval_drift exceeds max: drift={drift} max={args.max_train_eval_drift}")

    if args.require_train_gate_pass and best.get("train_gate_passes") is not True:
        alarms.append("best_profile.train_gate_passes is not true")
    if args.require_replay_gate_pass and best.get("replay_gate_passes") is not True:
        alarms.append("best_profile.replay_gate_passes is not true")
    if args.require_drift_gate_pass and best.get("drift_passes") is not True:
        alarms.append("best_profile.drift_passes is not true")

    required_thresholds = {
        "llt_min_mmlu_test_acc": args.min_train_mmlu,
        "llt_min_conversational_test_acc": args.min_train_conversational,
        "llt_min_eval_mmlu_acc": args.min_eval_mmlu,
        "llt_min_eval_conversational_acc": args.min_eval_conversational,
    }
    for key, expected_min in required_thresholds.items():
        current = as_float(split_gates.get(key))
        if current is None:
            alarms.append(f"split_gates.{key} missing/non-numeric")
            continue
        if current < expected_min:
            alarms.append(f"split threshold weakened: {key} current={current} expected_min={expected_min}")

    out = {
        "status": "ok" if not alarms else "alarm",
        "summary": str(args.summary),
        "expected_profile": args.expected_profile,
        "best_profile": best_profile,
        "best_rank_metric_value": best.get("rank_metric_value"),
        "train_eval_drift": drift,
        "max_train_eval_drift": args.max_train_eval_drift,
        "split_gates": split_gates,
        "alarms": alarms,
    }
    print(json.dumps(out, indent=2, ensure_ascii=True))
    return 0 if not alarms else 6


if __name__ == "__main__":
    raise SystemExit(main())
