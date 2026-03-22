#!/usr/bin/env python3
"""Evaluate intelligence scoring artifacts against configurable readiness thresholds."""

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


def parse_states(raw: str) -> list[str]:
    states = [s.strip() for s in raw.split(",")]
    return [s for s in states if s]


def maybe_fail(enabled: bool, code: int) -> int:
    return code if enabled else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check intelligence readiness from scoring artifact")
    parser.add_argument("--score-json", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-ml-score", type=float, required=False, default=None)
    parser.add_argument("--min-logic-chain-score", type=float, required=False, default=None)
    parser.add_argument("--min-ai-score", type=float, required=False, default=None)
    parser.add_argument("--min-agi-readiness-score", type=float, required=False, default=None)
    parser.add_argument("--max-contested-ratio", type=float, required=False, default=None)
    parser.add_argument("--allowed-decision-states", type=str, required=False, default="")
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    payload = load_json(args.score_json)
    if not payload:
        out = {
            "status": "alarm",
            "reason": "missing_or_invalid_score_json",
            "score_json": str(args.score_json),
            "enforce": args.enforce,
            "failures": ["Missing or invalid intelligence scoring JSON payload."],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=True))
        return maybe_fail(args.enforce, 9)

    scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
    governance = payload.get("components", {}).get("governance")
    governance = governance if isinstance(governance, dict) else {}

    ml_score = as_float(scores.get("ml_intelligence_score"))
    logic_score = as_float(scores.get("logic_chain_score"))
    ai_score = as_float(scores.get("ai_intelligence_score"))
    agi_score = as_float(scores.get("agi_readiness_score"))
    contested_ratio = as_float(governance.get("contested_ratio_recent"))
    decision_state = payload.get("decision_state") if isinstance(payload.get("decision_state"), str) else None

    failures: list[str] = []
    checks: dict[str, bool | None] = {}

    def check_min(name: str, value: float | None, threshold: float | None) -> None:
        if threshold is None:
            checks[name] = None
            return
        if value is None:
            checks[name] = False
            failures.append(f"{name} missing; required >= {threshold}")
            return
        passed = value >= threshold
        checks[name] = passed
        if not passed:
            failures.append(f"{name} below threshold: {value} < {threshold}")

    check_min("ml_intelligence_score", ml_score, args.min_ml_score)
    check_min("logic_chain_score", logic_score, args.min_logic_chain_score)
    check_min("ai_intelligence_score", ai_score, args.min_ai_score)
    check_min("agi_readiness_score", agi_score, args.min_agi_readiness_score)

    if args.max_contested_ratio is None:
        checks["contested_ratio_recent"] = None
    elif contested_ratio is None:
        checks["contested_ratio_recent"] = False
        failures.append("contested_ratio_recent missing; max threshold was provided")
    else:
        contested_ok = contested_ratio <= args.max_contested_ratio
        checks["contested_ratio_recent"] = contested_ok
        if not contested_ok:
            failures.append(
                f"contested_ratio_recent above threshold: {contested_ratio} > {args.max_contested_ratio}"
            )

    allowed_states = parse_states(args.allowed_decision_states)
    if not allowed_states:
        checks["decision_state_allowed"] = None
    else:
        allowed = isinstance(decision_state, str) and decision_state in allowed_states
        checks["decision_state_allowed"] = allowed
        if not allowed:
            failures.append(f"decision_state not in allowed set: {decision_state!r} not in {allowed_states!r}")

    status = "ok" if not failures else "alarm"
    out = {
        "status": status,
        "enforce": args.enforce,
        "score_json": str(args.score_json),
        "scores": {
            "ml_intelligence_score": ml_score,
            "logic_chain_score": logic_score,
            "ai_intelligence_score": ai_score,
            "agi_readiness_score": agi_score,
        },
        "governance": {
            "decision_state": decision_state,
            "contested_ratio_recent": contested_ratio,
        },
        "thresholds": {
            "min_ml_score": args.min_ml_score,
            "min_logic_chain_score": args.min_logic_chain_score,
            "min_ai_score": args.min_ai_score,
            "min_agi_readiness_score": args.min_agi_readiness_score,
            "max_contested_ratio": args.max_contested_ratio,
            "allowed_decision_states": allowed_states,
        },
        "checks": checks,
        "failures": failures,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=True))
    if failures:
        return maybe_fail(args.enforce, 9)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
