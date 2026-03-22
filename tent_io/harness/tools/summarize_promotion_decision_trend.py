#!/usr/bin/env python3
"""Summarize promotion decision-state history for quick regime tracking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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


def normalize_state(row: dict[str, Any]) -> str:
    state = row.get("decision_state")
    if isinstance(state, str) and state:
        return state
    if row.get("contested") is True:
        return "contested"
    if row.get("aligned") is True:
        return "aligned_unknown"
    return "insufficient_signal"


def count_states(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        state = normalize_state(row)
        counts[state] = counts.get(state, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize promotion decision-state trend history")
    parser.add_argument("--history", type=Path, required=True, help="promotion_decision.history.ndjson")
    parser.add_argument("--out-json", type=Path, required=True, help="trend summary JSON")
    parser.add_argument("--out-md", type=Path, required=True, help="trend summary markdown")
    parser.add_argument("--window", type=int, default=20, help="Recent-row window for short trend")
    args = parser.parse_args()

    if args.window < 1:
        raise SystemExit("--window must be >= 1")

    rows = parse_history(args.history)
    recent = rows[-args.window :]
    counts_all = count_states(rows)
    counts_recent = count_states(recent)
    latest_state = normalize_state(rows[-1]) if rows else "insufficient_signal"

    contested_ratio_recent = 0.0
    if recent:
        contested_ratio_recent = counts_recent.get("contested", 0) / float(len(recent))

    regime_label = "balanced"
    if contested_ratio_recent >= 0.6:
        regime_label = "contested_dominant"
    elif contested_ratio_recent <= 0.2 and latest_state.startswith("aligned"):
        regime_label = "aligned_dominant"

    out = {
        "status": "ok",
        "history_path": str(args.history),
        "total_points": len(rows),
        "window": args.window,
        "window_points": len(recent),
        "latest_state": latest_state,
        "counts_all": counts_all,
        "counts_recent": counts_recent,
        "contested_ratio_recent": contested_ratio_recent,
        "regime_label": regime_label,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    lines = [
        "# Promotion Decision Trend",
        "",
        f"- total_points: `{out['total_points']}`",
        f"- window: `{out['window']}`",
        f"- window_points: `{out['window_points']}`",
        f"- latest_state: `{out['latest_state']}`",
        f"- contested_ratio_recent: `{out['contested_ratio_recent']}`",
        f"- regime_label: `{out['regime_label']}`",
        f"- counts_recent: `{out['counts_recent']}`",
        f"- counts_all: `{out['counts_all']}`",
    ]
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out_json": str(args.out_json), "out_md": str(args.out_md)}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
