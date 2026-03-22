#!/usr/bin/env python3
"""Regression delta gate for expansion best-profile metrics."""

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
        raise SystemExit(f"Expected JSON object: {path}")
    return payload


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def best_metrics(payload: dict[str, Any]) -> dict[str, float | None]:
    best = payload.get("best_profile")
    if not isinstance(best, dict):
        return {
            "final_test_acc": None,
            "mmlu_test_acc": None,
            "conversational_logic_test_acc": None,
            "drift": None,
        }
    return {
        "final_test_acc": as_float(best.get("final_test_acc")),
        "mmlu_test_acc": as_float(best.get("final_mmlu_test_acc")),
        "conversational_logic_test_acc": as_float(best.get("final_conversational_logic_test_acc")),
        "drift": as_float(best.get("train_eval_drift")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Regression delta checks for LLT expansion best profile")
    parser.add_argument("--current", type=Path, required=True, help="Current sweep summary JSON.")
    parser.add_argument("--previous", type=Path, required=True, help="Previous/baseline sweep summary JSON.")
    parser.add_argument("--min-delta-final-test-acc", type=float, default=-0.01)
    parser.add_argument("--min-delta-mmlu-test-acc", type=float, default=-0.01)
    parser.add_argument("--min-delta-conversational-test-acc", type=float, default=-0.02)
    parser.add_argument("--max-delta-drift", type=float, default=0.0, help="Allowed absolute drift delta.")
    args = parser.parse_args()

    current = load_json(args.current)
    previous = load_json(args.previous)
    cur = best_metrics(current)
    prev = best_metrics(previous)
    previous_missing = all(value is None for value in prev.values())
    if previous_missing:
        out = {
            "status": "skipped",
            "reason": "missing_previous_metrics",
            "current": str(args.current),
            "previous": str(args.previous),
            "current_metrics": cur,
            "previous_metrics": prev,
        }
        print(json.dumps(out, indent=2, ensure_ascii=True))
        return 0

    deltas = {
        "delta_final_test_acc": None,
        "delta_mmlu_test_acc": None,
        "delta_conversational_logic_test_acc": None,
        "delta_drift": None,
    }
    failures: list[str] = []

    pairs = [
        ("final_test_acc", "delta_final_test_acc", args.min_delta_final_test_acc),
        ("mmlu_test_acc", "delta_mmlu_test_acc", args.min_delta_mmlu_test_acc),
        ("conversational_logic_test_acc", "delta_conversational_logic_test_acc", args.min_delta_conversational_test_acc),
    ]
    for metric, delta_key, minimum in pairs:
        c = cur.get(metric)
        p = prev.get(metric)
        if c is None or p is None:
            failures.append(f"Missing metric for delta check: {metric}")
            continue
        delta = float(c) - float(p)
        deltas[delta_key] = delta
        if delta < minimum:
            failures.append(f"{metric} regression beyond threshold: delta={delta} < {minimum}")

    c_drift = cur.get("drift")
    p_drift = prev.get("drift")
    if c_drift is None or p_drift is None:
        failures.append("Missing metric for delta check: drift")
    else:
        d_drift = abs(float(c_drift) - float(p_drift))
        deltas["delta_drift"] = d_drift
        if d_drift > args.max_delta_drift:
            failures.append(f"absolute drift delta beyond threshold: delta={d_drift} > {args.max_delta_drift}")

    out = {
        "status": "ok" if not failures else "alarm",
        "current": str(args.current),
        "previous": str(args.previous),
        "current_metrics": cur,
        "previous_metrics": prev,
        "deltas": deltas,
        "thresholds": {
            "min_delta_final_test_acc": args.min_delta_final_test_acc,
            "min_delta_mmlu_test_acc": args.min_delta_mmlu_test_acc,
            "min_delta_conversational_test_acc": args.min_delta_conversational_test_acc,
            "max_delta_drift": args.max_delta_drift,
        },
        "failures": failures,
    }
    print(json.dumps(out, indent=2, ensure_ascii=True))
    return 0 if not failures else 8


if __name__ == "__main__":
    raise SystemExit(main())
