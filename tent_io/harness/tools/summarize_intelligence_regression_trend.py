#!/usr/bin/env python3
"""Summarize intelligence regression history and optionally enforce trend limits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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


def row_status(row: dict[str, Any]) -> str:
    status = row.get("status")
    if isinstance(status, str) and status:
        return status
    return "unknown"


def consecutive_alarms(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in reversed(rows):
        if row_status(row) == "alarm":
            count += 1
            continue
        break
    return count


def maybe_fail(enforce: bool, code: int) -> int:
    return code if enforce else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize intelligence regression trend history")
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--max-alarm-ratio", type=float, default=None)
    parser.add_argument("--max-consecutive-alarms", type=int, default=None)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    if args.window < 1:
        raise SystemExit("--window must be >= 1")
    if args.max_consecutive_alarms is not None and args.max_consecutive_alarms < 0:
        raise SystemExit("--max-consecutive-alarms must be >= 0")

    rows = parse_history(args.history)
    recent = rows[-args.window :]
    latest = row_status(rows[-1]) if rows else "missing"

    alarm_all = sum(1 for row in rows if row_status(row) == "alarm")
    skipped_all = sum(1 for row in rows if row_status(row) == "skipped")
    ok_all = sum(1 for row in rows if row_status(row) == "ok")

    alarm_recent = sum(1 for row in recent if row_status(row) == "alarm")
    skipped_recent = sum(1 for row in recent if row_status(row) == "skipped")
    ok_recent = sum(1 for row in recent if row_status(row) == "ok")

    alarm_ratio_recent = (alarm_recent / float(len(recent))) if recent else 0.0
    consecutive_alarm_recent = consecutive_alarms(recent)

    failures: list[str] = []
    checks: dict[str, bool | None] = {}

    if args.max_alarm_ratio is None:
        checks["max_alarm_ratio"] = None
    else:
        pass_ratio = alarm_ratio_recent <= args.max_alarm_ratio
        checks["max_alarm_ratio"] = pass_ratio
        if not pass_ratio:
            failures.append(
                f"alarm_ratio_recent above threshold: {alarm_ratio_recent} > {args.max_alarm_ratio}"
            )

    if args.max_consecutive_alarms is None:
        checks["max_consecutive_alarms"] = None
    else:
        pass_consecutive = consecutive_alarm_recent <= args.max_consecutive_alarms
        checks["max_consecutive_alarms"] = pass_consecutive
        if not pass_consecutive:
            failures.append(
                "consecutive_alarm_recent above threshold: "
                f"{consecutive_alarm_recent} > {args.max_consecutive_alarms}"
            )

    regime_label = "stable_or_sparse"
    if alarm_ratio_recent >= 0.5:
        regime_label = "degrading_dominant"
    elif alarm_ratio_recent >= 0.2:
        regime_label = "mixed_signal"

    out = {
        "status": "ok" if not failures else "alarm",
        "enforce": args.enforce,
        "history_path": str(args.history),
        "total_points": len(rows),
        "window": args.window,
        "window_points": len(recent),
        "latest_status": latest,
        "counts_all": {
            "ok": ok_all,
            "alarm": alarm_all,
            "skipped": skipped_all,
        },
        "counts_recent": {
            "ok": ok_recent,
            "alarm": alarm_recent,
            "skipped": skipped_recent,
        },
        "alarm_ratio_recent": alarm_ratio_recent,
        "consecutive_alarm_recent": consecutive_alarm_recent,
        "regime_label": regime_label,
        "thresholds": {
            "max_alarm_ratio": args.max_alarm_ratio,
            "max_consecutive_alarms": args.max_consecutive_alarms,
        },
        "checks": checks,
        "failures": failures,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    lines = [
        "# Intelligence Regression Trend",
        "",
        f"- status: `{out['status']}`",
        f"- total_points: `{out['total_points']}`",
        f"- window: `{out['window']}`",
        f"- window_points: `{out['window_points']}`",
        f"- latest_status: `{out['latest_status']}`",
        f"- alarm_ratio_recent: `{out['alarm_ratio_recent']}`",
        f"- consecutive_alarm_recent: `{out['consecutive_alarm_recent']}`",
        f"- regime_label: `{out['regime_label']}`",
        f"- counts_recent: `{out['counts_recent']}`",
        f"- counts_all: `{out['counts_all']}`",
        f"- failures: `{out['failures']}`",
    ]
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": out["status"], "out_json": str(args.out_json), "out_md": str(args.out_md)}, indent=2, ensure_ascii=True))
    if failures:
        return maybe_fail(args.enforce, 11)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
