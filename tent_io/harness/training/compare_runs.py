#!/usr/bin/env python3
"""Compare unified Phase-1 training runs and print a leaderboard."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def load_report(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_metric(report: dict[str, Any], key: str) -> float:
    final = report.get("final_metrics", {})
    v = final.get(key)
    if isinstance(v, (int, float)):
        return float(v)
    return float("-inf")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare unified Phase-1 runs")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/training"),
        help="Directory that contains unified_phase1_* subdirectories.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="How many top rows to show in the leaderboard.",
    )
    parser.add_argument(
        "--sort-by",
        choices=["mmlu", "gsm_answer", "gsm_op"],
        default="mmlu",
        help="Primary metric for ranking.",
    )
    parser.add_argument(
        "--update-best-links",
        action="store_true",
        help="Update best_* symlinks in reports dir for all metrics.",
    )
    parser.add_argument(
        "--write-summary-json",
        action="store_true",
        help="Write leaderboard_summary.json in reports dir.",
    )
    args = parser.parse_args()

    metric_key = {
        "mmlu": "final_mmlu_test_acc",
        "gsm_answer": "final_gsm_answer_test_acc",
        "gsm_op": "final_gsm_op_test_acc",
    }[args.sort_by]

    runs: list[dict[str, Any]] = []
    if not args.reports_dir.exists():
        print("No reports directory found.")
        return 0

    for run_dir in sorted(args.reports_dir.glob("unified_phase1_*")):
        report_path = run_dir / "report.json"
        report = load_report(report_path)
        if not report:
            continue
        final = report.get("final_metrics", {})
        row = {
            "run_id": report.get("run_id", run_dir.name),
            "mmlu": float(final.get("final_mmlu_test_acc", float("-inf"))),
            "gsm_answer": float(final.get("final_gsm_answer_test_acc", float("-inf"))),
            "gsm_op": float(final.get("final_gsm_op_test_acc", float("-inf"))),
            "mmlu_rows": int(final.get("mmlu_train_rows", 0)),
            "gsm_rows": int(final.get("gsm_train_rows", 0)),
            "path": str(run_dir),
        }
        runs.append(row)

    if not runs:
        print("No valid run reports found.")
        return 0

    runs.sort(key=lambda r: r[args.sort_by], reverse=True)

    print(f"Leaderboard (sort_by={args.sort_by}, metric={metric_key})")
    print("rank | run_id               | mmlu   | gsm_ans | gsm_op  | mmlu_rows | gsm_rows")
    print("-----+----------------------+--------+---------+---------+-----------+---------")
    for i, r in enumerate(runs[: args.top_k], start=1):
        def fmt(v: float) -> str:
            return "n/a".ljust(7) if v == float("-inf") else f"{v:0.4f}".ljust(7)

        print(
            f"{str(i).rjust(4)} | "
            f"{r['run_id'][:20].ljust(20)} | "
            f"{fmt(r['mmlu'])} | "
            f"{fmt(r['gsm_answer'])} | "
            f"{fmt(r['gsm_op'])} | "
            f"{str(r['mmlu_rows']).rjust(9)} | "
            f"{str(r['gsm_rows']).rjust(7)}"
        )

    best = runs[0]
    summary = {
        "best_run_id": best["run_id"],
        "best_metric": args.sort_by,
        "best_metric_value": best[args.sort_by],
        "best_path": best["path"],
        "num_runs": len(runs),
    }
    print("\n" + json.dumps(summary, indent=2))

    if args.write_summary_json:
        summary_path = args.reports_dir / "leaderboard_summary.json"
        payload = {
            "sorted_by": args.sort_by,
            "num_runs": len(runs),
            "best": summary,
            "runs": runs,
        }
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)
        print(f"Wrote summary: {summary_path}")

    if args.update_best_links:
        metric_to_key = {
            "best_mmlu": "mmlu",
            "best_gsm_answer": "gsm_answer",
            "best_gsm_op": "gsm_op",
        }
        for link_name, key in metric_to_key.items():
            valid = [r for r in runs if r[key] != float("-inf")]
            if not valid:
                continue
            valid.sort(key=lambda r: r[key], reverse=True)
            target = Path(valid[0]["path"])
            link_path = args.reports_dir / link_name
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            # Use relative symlink so directories can be moved together.
            rel_target = os.path.relpath(target, start=args.reports_dir)
            link_path.symlink_to(rel_target)
            print(f"Updated {link_name} -> {rel_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
