#!/usr/bin/env python3
"""Compare voxel/vixel/vexel/boxels logic-chain training runs."""

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


def metric(row: dict[str, Any], key: str) -> float:
    v = row.get(key, float("-inf"))
    if isinstance(v, (int, float)):
        return float(v)
    return float("-inf")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare voxel stack logic training runs")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/training"),
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--sort-by",
        choices=["stack", "hybrid_step", "rule_step"],
        default="hybrid_step",
    )
    parser.add_argument("--update-best-links", action="store_true")
    parser.add_argument("--write-summary-json", action="store_true")
    args = parser.parse_args()

    runs: list[dict[str, Any]] = []
    for run_dir in sorted(args.reports_dir.glob("voxel_stack_logic_*")):
        report = load_report(run_dir / "report.json")
        if not report:
            continue
        final = report.get("final_metrics", {})
        runs.append(
            {
                "run_id": str(final.get("run_id", run_dir.name)),
                "stack": float(final.get("stack_test_acc", float("-inf"))),
                "hybrid_step": float(final.get("hybrid_step_test_acc", float("-inf"))),
                "rule_step": float(final.get("rule_step_given_true_stack_acc", float("-inf"))),
                "rows_train": int(final.get("rows_train", 0)),
                "rows_test": int(final.get("rows_test", 0)),
                "path": str(run_dir),
            }
        )

    if not runs:
        print("No voxel stack reports found.")
        return 0

    runs.sort(key=lambda r: metric(r, args.sort_by), reverse=True)
    print(f"Voxel leaderboard (sort_by={args.sort_by})")
    print("rank | run_id               | stack  | hybrid | rule   | rows_train | rows_test")
    print("-----+----------------------+--------+--------+--------+------------+----------")
    for i, r in enumerate(runs[: args.top_k], start=1):
        def fmt(v: float) -> str:
            return "n/a".ljust(6) if v == float("-inf") else f"{v:0.4f}".ljust(6)

        print(
            f"{str(i).rjust(4)} | {r['run_id'][:20].ljust(20)} | {fmt(r['stack'])} | "
            f"{fmt(r['hybrid_step'])} | {fmt(r['rule_step'])} | "
            f"{str(r['rows_train']).rjust(10)} | {str(r['rows_test']).rjust(8)}"
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
        out = args.reports_dir / "voxel_leaderboard_summary.json"
        with out.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "sorted_by": args.sort_by,
                    "num_runs": len(runs),
                    "best": summary,
                    "runs": runs,
                },
                f,
                indent=2,
                ensure_ascii=True,
            )
        print(f"Wrote summary: {out}")

    if args.update_best_links:
        metric_map = {
            "best_voxel_stack": "stack",
            "best_voxel_hybrid_step": "hybrid_step",
            "best_voxel_rule_step": "rule_step",
        }
        for link_name, key in metric_map.items():
            valid = [r for r in runs if r[key] != float("-inf")]
            if not valid:
                continue
            valid.sort(key=lambda r: r[key], reverse=True)
            target = Path(valid[0]["path"])
            link_path = args.reports_dir / link_name
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            rel_target = os.path.relpath(target, start=args.reports_dir)
            link_path.symlink_to(rel_target)
            print(f"Updated {link_name} -> {rel_target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
