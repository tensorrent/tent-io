#!/usr/bin/env python3
"""Compute a unified promotion advisory state from governance and intelligence signals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def status_of(payload: dict[str, Any]) -> str:
    status = payload.get("status")
    return status if isinstance(status, str) and status else "missing"


def parse_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute promotion advisory state from decision and intelligence checks")
    parser.add_argument("--promotion-decision", type=Path, required=True)
    parser.add_argument("--intelligence-readiness", type=Path, required=False, default=None)
    parser.add_argument("--intelligence-regression", type=Path, required=False, default=None)
    parser.add_argument("--intelligence-regression-trend", type=Path, required=False, default=None)
    parser.add_argument("--history-out", type=Path, required=False, default=None)
    parser.add_argument("--required-promote-candidate-streak", type=int, required=False, default=1)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    args = parser.parse_args()
    if args.required_promote_candidate_streak < 1:
        raise SystemExit("--required-promote-candidate-streak must be >= 1")

    decision = load_json(args.promotion_decision)
    readiness = load_json(args.intelligence_readiness)
    regression = load_json(args.intelligence_regression)
    regression_trend = load_json(args.intelligence_regression_trend)

    decision_state = decision.get("decision_state") if isinstance(decision.get("decision_state"), str) else "missing"
    promotion_allowed = decision.get("promotion_allowed") is True

    readiness_status = status_of(readiness)
    regression_status = status_of(regression)
    regression_trend_status = status_of(regression_trend)

    reasons: list[str] = []
    advisory_state_base = "observe"

    hard_block = False
    if decision_state in {"contested", "insufficient_signal", "missing"}:
        hard_block = True
        reasons.append(f"decision_state={decision_state}")
    if not promotion_allowed:
        hard_block = True
        reasons.append("promotion_allowed=false")

    for name, status in (
        ("intelligence_readiness", readiness_status),
        ("intelligence_regression", regression_status),
        ("intelligence_regression_trend", regression_trend_status),
    ):
        if status == "alarm":
            hard_block = True
            reasons.append(f"{name}=alarm")

    if hard_block:
        advisory_state_base = "hold"
    else:
        statuses = [readiness_status, regression_status, regression_trend_status]
        all_ok = all(s == "ok" for s in statuses)
        if all_ok:
            advisory_state_base = "promote_candidate"
            reasons.append("all_signals_ok")
        else:
            advisory_state_base = "observe"
            reasons.append("partial_signal_or_skipped")

    # Optional hysteresis: require streak for promote_candidate.
    promote_candidate_streak = 0
    if advisory_state_base == "promote_candidate":
        history_rows = parse_history(args.history_out) if args.history_out else []
        promote_candidate_streak = 1
        for row in reversed(history_rows):
            prev_state = row.get("advisory_state_base")
            if prev_state == "promote_candidate":
                promote_candidate_streak += 1
                continue
            break
    advisory_state = advisory_state_base
    if (
        advisory_state_base == "promote_candidate"
        and promote_candidate_streak < args.required_promote_candidate_streak
    ):
        advisory_state = "observe"
        reasons.append(
            "promote_candidate_pending_streak:"
            f"{promote_candidate_streak}/{args.required_promote_candidate_streak}"
        )

    out = {
        "status": "ok",
        "advisory_state": advisory_state,
        "advisory_state_base": advisory_state_base,
        "promote_candidate_streak": promote_candidate_streak,
        "required_promote_candidate_streak": args.required_promote_candidate_streak,
        "promotion_decision_state": decision_state,
        "promotion_allowed": promotion_allowed,
        "signal_status": {
            "intelligence_readiness": readiness_status,
            "intelligence_regression": regression_status,
            "intelligence_regression_trend": regression_trend_status,
        },
        "inputs": {
            "promotion_decision": str(args.promotion_decision),
            "intelligence_readiness": str(args.intelligence_readiness) if args.intelligence_readiness else None,
            "intelligence_regression": str(args.intelligence_regression) if args.intelligence_regression else None,
            "intelligence_regression_trend": str(args.intelligence_regression_trend) if args.intelligence_regression_trend else None,
        },
        "reasons": reasons,
    }
    if args.history_out:
        history_row = dict(out)
        args.history_out.parent.mkdir(parents=True, exist_ok=True)
        with args.history_out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(history_row, ensure_ascii=True) + "\n")

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    lines = [
        "# Intelligence Promotion Advisory",
        "",
        f"- advisory_state: `{advisory_state}`",
        f"- advisory_state_base: `{advisory_state_base}`",
        f"- promote_candidate_streak: `{promote_candidate_streak}`",
        f"- required_promote_candidate_streak: `{args.required_promote_candidate_streak}`",
        f"- promotion_decision_state: `{decision_state}`",
        f"- promotion_allowed: `{promotion_allowed}`",
        f"- intelligence_readiness_status: `{readiness_status}`",
        f"- intelligence_regression_status: `{regression_status}`",
        f"- intelligence_regression_trend_status: `{regression_trend_status}`",
        f"- reasons: `{reasons}`",
    ]
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "advisory_state": advisory_state, "out_json": str(args.out_json)}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
