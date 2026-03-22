#!/usr/bin/env python3
"""Compare liquid language model training runs and update best links."""

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


def metric_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return float("-inf")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare liquid language model runs")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/training"),
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--sort-by",
        choices=["final_test_acc", "mmlu_test_acc", "conversational_logic_test_acc"],
        default="final_test_acc",
    )
    parser.add_argument("--update-best-links", action="store_true")
    parser.add_argument("--write-summary-json", action="store_true")
    args = parser.parse_args()

    runs: list[dict[str, Any]] = []
    for run_dir in sorted(args.reports_dir.glob("liquid_llt_*")):
        report = load_report(run_dir / "report.json")
        if not report:
            continue
        final = report.get("final_metrics", {})
        runs.append(
            {
                "run_id": str(final.get("run_id", run_dir.name)),
                "test_acc": metric_float(final.get("final_test_acc", float("-inf"))),
                "mmlu_test_acc": metric_float(final.get("final_mmlu_test_acc", float("-inf"))),
                "conversational_logic_test_acc": metric_float(
                    final.get("final_conversational_logic_test_acc", float("-inf"))
                ),
                "rows_train": int(final.get("rows_train", 0)),
                "rows_test": int(final.get("rows_test", 0)),
                "rows_merkle_replay": int(final.get("rows_merkle_replay", 0)),
                "hidden_dim": int(final.get("hidden_dim", 0)),
                "path": str(run_dir),
            }
        )

    if not runs:
        print("No liquid LLM reports found.")
        return 0

    sort_key_map = {
        "final_test_acc": "test_acc",
        "mmlu_test_acc": "mmlu_test_acc",
        "conversational_logic_test_acc": "conversational_logic_test_acc",
    }
    sort_key = sort_key_map[args.sort_by]
    runs.sort(key=lambda r: r[sort_key], reverse=True)
    print(f"Liquid leaderboard (sort_by={args.sort_by})")
    print("rank | run_id               | test   | mmlu   | conv   | rows_train | rows_test | merkle | hidden")
    print("-----+----------------------+--------+--------+--------+------------+-----------+--------+-------")
    for i, r in enumerate(runs[: args.top_k], start=1):
        def fmt(v: float) -> str:
            return "n/a".ljust(6) if v == float("-inf") else f"{v:0.4f}".ljust(6)

        print(
            f"{str(i).rjust(4)} | {r['run_id'][:20].ljust(20)} | {fmt(r['test_acc'])} | "
            f"{fmt(r['mmlu_test_acc'])} | {fmt(r['conversational_logic_test_acc'])} | "
            f"{str(r['rows_train']).rjust(10)} | {str(r['rows_test']).rjust(9)} | "
            f"{str(r['rows_merkle_replay']).rjust(6)} | {str(r['hidden_dim']).rjust(5)}"
        )

    best = runs[0]
    summary = {
        "best_run_id": best["run_id"],
        "best_metric": args.sort_by,
        "best_metric_value": best[sort_key],
        "best_path": best["path"],
        "num_runs": len(runs),
    }
    print("\n" + json.dumps(summary, indent=2))

    if args.write_summary_json:
        out = args.reports_dir / "liquid_leaderboard_summary.json"
        payload = {
            "sorted_by": args.sort_by,
            "num_runs": len(runs),
            "best": summary,
            "runs": runs,
        }
        with out.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=True)
        print(f"Wrote summary: {out}")

    if args.update_best_links:
        link_path = args.reports_dir / "best_liquid_llt"
        target = Path(best["path"])
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        rel_target = os.path.relpath(target, start=args.reports_dir)
        link_path.symlink_to(rel_target)
        print(f"Updated best_liquid_llt -> {rel_target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
