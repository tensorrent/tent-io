#!/usr/bin/env python3
"""Regression delta checks for intelligence scoring artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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


def maybe_fail(enforce: bool, code: int) -> int:
    return code if enforce else 0


def extract(payload: dict[str, Any]) -> dict[str, float | None]:
    scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
    governance = payload.get("components", {}).get("governance")
    governance = governance if isinstance(governance, dict) else {}
    return {
        "ml_intelligence_score": as_float(scores.get("ml_intelligence_score")),
        "logic_chain_score": as_float(scores.get("logic_chain_score")),
        "ai_intelligence_score": as_float(scores.get("ai_intelligence_score")),
        "agi_readiness_score": as_float(scores.get("agi_readiness_score")),
        "contested_ratio_recent": as_float(governance.get("contested_ratio_recent")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check score deltas against previous intelligence scoring artifact")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-delta-ml-score", type=float, default=None)
    parser.add_argument("--min-delta-logic-chain-score", type=float, default=None)
    parser.add_argument("--min-delta-ai-score", type=float, default=None)
    parser.add_argument("--min-delta-agi-readiness-score", type=float, default=None)
    parser.add_argument("--max-delta-contested-ratio", type=float, default=None)
    parser.add_argument("--history-out", type=Path, required=False, default=None)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    current_payload = load_json(args.current)
    previous_payload = load_json(args.previous)
    cur = extract(current_payload)
    prev = extract(previous_payload)

    if not current_payload:
        out = {
            "status": "alarm",
            "reason": "missing_or_invalid_current",
            "current": str(args.current),
            "previous": str(args.previous),
            "enforce": args.enforce,
            "failures": ["Current intelligence scoring artifact is missing or invalid."],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        if args.history_out:
            row = dict(out)
            row["timestamp_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            args.history_out.parent.mkdir(parents=True, exist_ok=True)
            with args.history_out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")
        print(json.dumps(out, indent=2, ensure_ascii=True))
        return maybe_fail(args.enforce, 10)

    if not previous_payload:
        out = {
            "status": "skipped",
            "reason": "missing_or_invalid_previous",
            "current": str(args.current),
            "previous": str(args.previous),
            "enforce": args.enforce,
            "current_metrics": cur,
            "previous_metrics": prev,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        if args.history_out:
            row = dict(out)
            row["timestamp_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            args.history_out.parent.mkdir(parents=True, exist_ok=True)
            with args.history_out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")
        print(json.dumps(out, indent=2, ensure_ascii=True))
        return 0

    deltas: dict[str, float | None] = {
        "delta_ml_intelligence_score": None,
        "delta_logic_chain_score": None,
        "delta_ai_intelligence_score": None,
        "delta_agi_readiness_score": None,
        "delta_contested_ratio_recent": None,
    }
    failures: list[str] = []
    checks: dict[str, bool | None] = {}

    score_pairs = [
        ("ml_intelligence_score", "delta_ml_intelligence_score", args.min_delta_ml_score),
        ("logic_chain_score", "delta_logic_chain_score", args.min_delta_logic_chain_score),
        ("ai_intelligence_score", "delta_ai_intelligence_score", args.min_delta_ai_score),
        ("agi_readiness_score", "delta_agi_readiness_score", args.min_delta_agi_readiness_score),
    ]

    for metric, delta_key, threshold in score_pairs:
        if threshold is None:
            checks[metric] = None
            continue
        c = cur.get(metric)
        p = prev.get(metric)
        if c is None or p is None:
            checks[metric] = False
            failures.append(f"{metric} delta unavailable; required minimum delta {threshold}")
            continue
        delta = float(c) - float(p)
        deltas[delta_key] = delta
        passed = delta >= threshold
        checks[metric] = passed
        if not passed:
            failures.append(f"{metric} regression beyond threshold: delta={delta} < {threshold}")

    if args.max_delta_contested_ratio is None:
        checks["contested_ratio_recent"] = None
    else:
        c_ratio = cur.get("contested_ratio_recent")
        p_ratio = prev.get("contested_ratio_recent")
        if c_ratio is None or p_ratio is None:
            checks["contested_ratio_recent"] = False
            failures.append(
                "contested_ratio_recent delta unavailable; required maximum delta "
                f"{args.max_delta_contested_ratio}"
            )
        else:
            d_ratio = float(c_ratio) - float(p_ratio)
            deltas["delta_contested_ratio_recent"] = d_ratio
            passed = d_ratio <= args.max_delta_contested_ratio
            checks["contested_ratio_recent"] = passed
            if not passed:
                failures.append(
                    "contested_ratio_recent increase beyond threshold: "
                    f"delta={d_ratio} > {args.max_delta_contested_ratio}"
                )

    out = {
        "status": "ok" if not failures else "alarm",
        "enforce": args.enforce,
        "current": str(args.current),
        "previous": str(args.previous),
        "current_metrics": cur,
        "previous_metrics": prev,
        "deltas": deltas,
        "thresholds": {
            "min_delta_ml_score": args.min_delta_ml_score,
            "min_delta_logic_chain_score": args.min_delta_logic_chain_score,
            "min_delta_ai_score": args.min_delta_ai_score,
            "min_delta_agi_readiness_score": args.min_delta_agi_readiness_score,
            "max_delta_contested_ratio": args.max_delta_contested_ratio,
        },
        "checks": checks,
        "failures": failures,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    if args.history_out:
        row = dict(out)
        row["timestamp_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        args.history_out.parent.mkdir(parents=True, exist_ok=True)
        with args.history_out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")
    print(json.dumps(out, indent=2, ensure_ascii=True))
    if failures:
        return maybe_fail(args.enforce, 10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
