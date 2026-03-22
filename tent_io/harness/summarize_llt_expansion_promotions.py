#!/usr/bin/env python3
"""Summarize LLT expansion pointer-promotion history into leaderboard artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except Exception:
            continue
    return rows


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize LLT expansion pointer-promotion history")
    parser.add_argument(
        "--history",
        type=Path,
        default=Path(
            "/Users/coo-koba42/dev/tent_io/harness/reports/expansion/llt_expansion_pointer_promotion_history.ndjson"
        ),
        help="Promotion history NDJSON path.",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path(
            "/Users/coo-koba42/dev/tent_io/harness/reports/expansion/llt_expansion_pointer_promotion_summary.current.json"
        ),
        help="Summary JSON output path.",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path(
            "/Users/coo-koba42/dev/tent_io/harness/reports/expansion/llt_expansion_pointer_promotion_summary.current.md"
        ),
        help="Summary markdown output path.",
    )
    parser.add_argument(
        "--sort-by",
        choices=["promotions", "avg_final_test_acc", "last_promoted_utc"],
        default="promotions",
        help="Leaderboard sort key (default: promotions).",
    )
    parser.add_argument(
        "--history-window",
        type=int,
        default=0,
        help="Use only the last N promotion events (0 means all history).",
    )
    args = parser.parse_args()

    rows = parse_ndjson(args.history)
    rows_total = len(rows)
    if args.history_window < 0:
        raise SystemExit("--history-window must be >= 0")
    if args.history_window > 0 and len(rows) > args.history_window:
        rows = rows[-args.history_window :]
    by_profile: dict[str, dict[str, Any]] = {}
    for row in rows:
        profile = row.get("after_profile")
        if not isinstance(profile, str) or not profile:
            continue
        entry = by_profile.setdefault(
            profile,
            {
                "profile": profile,
                "promotions": 0,
                "score_sum": 0.0,
                "score_count": 0,
                "last_promoted_utc": None,
                "last_job": None,
                "changed_promotions": 0,
            },
        )
        entry["promotions"] = int(entry["promotions"]) + 1
        score = as_float(row.get("after_final_test_acc"))
        if score is not None:
            entry["score_sum"] = float(entry["score_sum"]) + score
            entry["score_count"] = int(entry["score_count"]) + 1
        ts = row.get("timestamp_utc")
        if isinstance(ts, str):
            prev = entry.get("last_promoted_utc")
            if not isinstance(prev, str) or ts >= prev:
                entry["last_promoted_utc"] = ts
                job = row.get("job")
                entry["last_job"] = job if isinstance(job, str) else None
        if row.get("changed") is True:
            entry["changed_promotions"] = int(entry["changed_promotions"]) + 1

    leaderboard: list[dict[str, Any]] = []
    for profile, entry in by_profile.items():
        avg_score = None
        if int(entry["score_count"]) > 0:
            avg_score = float(entry["score_sum"]) / float(entry["score_count"])
        leaderboard.append(
            {
                "profile": profile,
                "promotions": int(entry["promotions"]),
                "avg_final_test_acc": avg_score,
                "last_promoted_utc": entry.get("last_promoted_utc"),
                "last_job": entry.get("last_job"),
                "changed_promotions": int(entry["changed_promotions"]),
            }
        )
    if args.sort_by == "last_promoted_utc":
        leaderboard.sort(
            key=lambda x: (
                str(x.get("last_promoted_utc") or ""),
                int(x.get("promotions", 0)),
                as_float(x.get("avg_final_test_acc")) or -1.0,
                str(x.get("profile", "")),
            ),
            reverse=True,
        )
    elif args.sort_by == "avg_final_test_acc":
        leaderboard.sort(
            key=lambda x: (
                as_float(x.get("avg_final_test_acc")) or -1.0,
                int(x.get("promotions", 0)),
                str(x.get("profile", "")),
            ),
            reverse=True,
        )
    else:
        leaderboard.sort(
            key=lambda x: (
                int(x.get("promotions", 0)),
                as_float(x.get("avg_final_test_acc")) or -1.0,
                str(x.get("profile", "")),
            ),
            reverse=True,
        )
    for i, row in enumerate(leaderboard, start=1):
        row["rank"] = i

    summary: dict[str, Any] = {
        "status": "ok",
        "history_path": str(args.history),
        "total_events_all_history": rows_total,
        "total_events": len(rows),
        "history_window": args.history_window,
        "profiles": len(leaderboard),
        "sort_by": args.sort_by,
        "leaderboard": leaderboard,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=True)

    lines: list[str] = []
    lines.append("# LLT Expansion Promotion Summary")
    lines.append("")
    lines.append(f"- history_path: `{args.history}`")
    lines.append(f"- total_events_all_history: `{rows_total}`")
    lines.append(f"- total_events: `{len(rows)}`")
    lines.append(f"- history_window: `{args.history_window}`")
    lines.append(f"- profiles: `{len(leaderboard)}`")
    lines.append(f"- sort_by: `{args.sort_by}`")
    lines.append("")
    lines.append("| rank | profile | promotions | avg_final_test_acc | last_promoted_utc | last_job | changed_promotions |")
    lines.append("|---:|---|---:|---:|---|---|---:|")
    for row in leaderboard:
        lines.append(
            "| {rank} | {profile} | {promotions} | {avg} | {last_ts} | {last_job} | {changed} |".format(
                rank=row.get("rank"),
                profile=row.get("profile"),
                promotions=row.get("promotions"),
                avg=row.get("avg_final_test_acc"),
                last_ts=row.get("last_promoted_utc"),
                last_job=row.get("last_job"),
                changed=row.get("changed_promotions"),
            )
        )
    if not leaderboard:
        lines.append("| - | - | 0 | - | - | - | 0 |")

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    with args.out_md.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(
        json.dumps(
            {
                "status": "ok",
                "out_json": str(args.out_json),
                "out_md": str(args.out_md),
                "profiles": len(leaderboard),
                "total_events_all_history": rows_total,
                "total_events": len(rows),
                "history_window": args.history_window,
                "sort_by": args.sort_by,
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
