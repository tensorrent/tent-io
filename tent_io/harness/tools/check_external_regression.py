#!/usr/bin/env python3
"""Compare external-eval profile artifacts and optionally enforce regressions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing JSON: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected object JSON: {path}")
    return payload


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def metric_map(payload: dict[str, Any]) -> dict[str, float | None]:
    metrics = payload.get("metrics")
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
    parser = argparse.ArgumentParser(description="Compare external eval artifacts (non-blocking by default).")
    parser.add_argument("--s1", type=Path, required=True, help="expand_s1 external eval JSON")
    parser.add_argument("--s2", type=Path, required=True, help="expand_s2 external eval JSON")
    parser.add_argument("--out", type=Path, required=True, help="comparison output JSON")
    parser.add_argument("--previous", type=Path, default=None, help="optional previous comparison JSON")
    parser.add_argument("--fail-on-regression", action="store_true", help="enable hard-fail regression mode")
    parser.add_argument("--min-delta-mmlu-pro", type=float, default=-0.02)
    parser.add_argument("--min-delta-gpqa", type=float, default=-0.02)
    parser.add_argument("--min-delta-long-context", type=float, default=-0.03)
    parser.add_argument("--min-delta-consistency", type=float, default=-0.05)
    args = parser.parse_args()

    s1 = load_json(args.s1)
    s2 = load_json(args.s2)
    s1m = metric_map(s1)
    s2m = metric_map(s2)

    deltas_s1_minus_s2: dict[str, float | None] = {}
    for key in s1m:
        a = s1m[key]
        b = s2m[key]
        deltas_s1_minus_s2[key] = None if a is None or b is None else (a - b)

    winner_votes = {"expand_s1": 0, "expand_s2": 0, "tie_or_missing": 0}
    for key, value in deltas_s1_minus_s2.items():
        if value is None:
            winner_votes["tie_or_missing"] += 1
        elif value > 0:
            winner_votes["expand_s1"] += 1
        elif value < 0:
            winner_votes["expand_s2"] += 1
        else:
            winner_votes["tie_or_missing"] += 1

    favored_profile = "tie_or_missing"
    if winner_votes["expand_s1"] > winner_votes["expand_s2"]:
        favored_profile = "expand_s1"
    elif winner_votes["expand_s2"] > winner_votes["expand_s1"]:
        favored_profile = "expand_s2"

    regression_failures: list[str] = []
    previous_loaded = None
    if args.previous is not None and args.previous.exists():
        previous_loaded = load_json(args.previous)
        prev_s1 = metric_map(previous_loaded.get("expand_s1") if isinstance(previous_loaded.get("expand_s1"), dict) else {})
        prev_s2 = metric_map(previous_loaded.get("expand_s2") if isinstance(previous_loaded.get("expand_s2"), dict) else {})
        thresholds = {
            "mmlu_pro_acc": args.min_delta_mmlu_pro,
            "gpqa_acc": args.min_delta_gpqa,
            "long_context_acc": args.min_delta_long_context,
            "consistency_score": args.min_delta_consistency,
        }
        for label, current_map, prev_map in (("expand_s1", s1m, prev_s1), ("expand_s2", s2m, prev_s2)):
            for key, minimum in thresholds.items():
                cur = current_map.get(key)
                prv = prev_map.get(key)
                if cur is None or prv is None:
                    continue
                delta = cur - prv
                if delta < minimum:
                    regression_failures.append(f"{label}.{key} regression: delta={delta} < {minimum}")

    out = {
        "status": "ok" if not regression_failures else "alarm",
        "mode": "comparison_non_blocking" if not args.fail_on_regression else "comparison_with_regression_gate",
        "expand_s1": s1,
        "expand_s2": s2,
        "deltas_s1_minus_s2": deltas_s1_minus_s2,
        "winner_votes": winner_votes,
        "favored_profile": favored_profile,
        "previous_compare_path": str(args.previous) if args.previous is not None else None,
        "regression_failures": regression_failures,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": out["status"], "out": str(args.out), "favored_profile": favored_profile}, indent=2, ensure_ascii=True))
    if regression_failures and args.fail_on_regression:
        return 9
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
