#!/usr/bin/env python3
"""Compute non-blocking promotion decision state from internal/external signals."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def parse_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def internal_margin_from_ranking(summary: dict[str, Any]) -> float | None:
    ranking = summary.get("ranking")
    if not isinstance(ranking, list) or len(ranking) < 2:
        return None
    top = ranking[0] if isinstance(ranking[0], dict) else {}
    nxt = ranking[1] if isinstance(ranking[1], dict) else {}
    top_metric = as_float(top.get("rank_metric_value"))
    next_metric = as_float(nxt.get("rank_metric_value"))
    if top_metric is None or next_metric is None:
        return None
    return top_metric - next_metric


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute non-blocking promotion decision state")
    parser.add_argument("--internal-summary", type=Path, required=True, help="llt_expansion_sweep.current.json")
    parser.add_argument("--external-compare", type=Path, required=True, help="external_eval_compare.current.json")
    parser.add_argument("--out", type=Path, required=True, help="decision output JSON")
    parser.add_argument("--history-out", type=Path, required=True, help="NDJSON decision history path")
    parser.add_argument("--alignment-required-runs", type=int, default=2)
    parser.add_argument("--min-internal-margin", type=float, default=0.0)
    parser.add_argument("--min-external-vote-margin", type=int, default=0)
    args = parser.parse_args()

    if args.alignment_required_runs < 1:
        raise SystemExit("--alignment-required-runs must be >= 1")

    internal = load_json(args.internal_summary)
    external = load_json(args.external_compare)

    best = internal.get("best_profile") if isinstance(internal.get("best_profile"), dict) else {}
    internal_winner = best.get("profile") if isinstance(best.get("profile"), str) else None
    external_winner = external.get("favored_profile") if isinstance(external.get("favored_profile"), str) else None
    votes = external.get("winner_votes") if isinstance(external.get("winner_votes"), dict) else {}

    internal_margin = internal_margin_from_ranking(internal)
    s1_votes = int(votes.get("expand_s1", 0) or 0)
    s2_votes = int(votes.get("expand_s2", 0) or 0)
    external_vote_margin = abs(s1_votes - s2_votes)

    valid_internal = isinstance(internal_winner, str) and internal_winner != ""
    valid_external = isinstance(external_winner, str) and external_winner not in {"", "tie_or_missing"}

    aligned = valid_internal and valid_external and internal_winner == external_winner
    contested = valid_internal and valid_external and internal_winner != external_winner
    meets_internal_margin = internal_margin is not None and internal_margin >= args.min_internal_margin
    meets_external_margin = external_vote_margin >= args.min_external_vote_margin

    history = parse_history(args.history_out)
    probe_record = {
        "internal_winner": internal_winner,
        "external_winner": external_winner,
        "aligned": aligned,
        "contested": contested,
    }
    history_with_current = history + [probe_record]
    aligned_streak = 0
    for row in reversed(history_with_current):
        if (
            isinstance(row, dict)
            and row.get("aligned") is True
            and row.get("internal_winner") == internal_winner
            and row.get("external_winner") == external_winner
        ):
            aligned_streak += 1
            continue
        break

    if not valid_internal or not valid_external:
        decision_state = "insufficient_signal"
    elif contested:
        decision_state = "contested"
    elif aligned and aligned_streak < args.alignment_required_runs:
        decision_state = "aligned_pending_confirmation"
    elif aligned and not (meets_internal_margin and meets_external_margin):
        decision_state = "aligned_but_margin_insufficient"
    else:
        decision_state = "aligned_ready_for_promotion"

    promotion_allowed = decision_state == "aligned_ready_for_promotion"
    record = {
        "timestamp_utc": now_utc(),
        "decision_state": decision_state,
        "promotion_allowed": promotion_allowed,
        "internal_winner": internal_winner,
        "external_winner": external_winner,
        "aligned": aligned,
        "contested": contested,
        "aligned_streak": aligned_streak,
        "alignment_required_runs": args.alignment_required_runs,
        "internal_margin": internal_margin,
        "external_vote_margin": external_vote_margin,
        "meets_internal_margin": meets_internal_margin,
        "meets_external_margin": meets_external_margin,
    }
    args.history_out.parent.mkdir(parents=True, exist_ok=True)
    with args.history_out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")

    out = {
        "status": "ok",
        "decision_state": decision_state,
        "promotion_allowed": promotion_allowed,
        "internal_winner": internal_winner,
        "external_winner": external_winner,
        "aligned": aligned,
        "contested": contested,
        "alignment_required_runs": args.alignment_required_runs,
        "aligned_streak": aligned_streak,
        "internal_margin": internal_margin,
        "min_internal_margin": args.min_internal_margin,
        "external_vote_margin": external_vote_margin,
        "min_external_vote_margin": args.min_external_vote_margin,
        "meets_internal_margin": meets_internal_margin,
        "meets_external_margin": meets_external_margin,
        "internal_summary": str(args.internal_summary),
        "external_compare": str(args.external_compare),
        "history_path": str(args.history_out),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(args.out), "decision_state": decision_state}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
