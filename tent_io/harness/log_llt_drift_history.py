#!/usr/bin/env python3
"""Append LLT drift summary rows to an NDJSON audit log."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Append LLT drift summary row to NDJSON history")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/full_stage_pipeline.current.json"),
        help="Pipeline JSON report path.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/llt_drift_history.ndjson"),
        help="NDJSON history output path.",
    )
    parser.add_argument(
        "--require-drift-pass",
        action="store_true",
        help="Exit nonzero when llt_drift_summary.drift_passes is not true.",
    )
    args = parser.parse_args()

    if not args.report.exists():
        raise SystemExit(f"Report not found: {args.report}")

    with args.report.open("r", encoding="utf-8") as f:
        report = json.load(f)
    if not isinstance(report, dict):
        raise SystemExit(f"Invalid report payload: {args.report}")

    summary = report.get("llt_drift_summary")
    if not isinstance(summary, dict):
        raise SystemExit("Missing llt_drift_summary in report.")

    drift_passes = summary.get("drift_passes")
    if args.require_drift_pass and drift_passes is not True:
        raise SystemExit("Drift assertion failed: llt_drift_summary.drift_passes is not true.")

    row: dict[str, Any] = {
        "run_id": report.get("run_id"),
        "timestamp_utc": report.get("timestamp_utc"),
        "status": report.get("status"),
        "strict": bool(report.get("strict", False)),
        "production": bool(report.get("production", False)),
        "report_path": str(args.report),
        "report_sha256": sha256_file(args.report),
        "llt_drift_summary": summary,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")

    print(
        json.dumps(
            {
                "status": "ok",
                "out": str(args.out),
                "run_id": report.get("run_id"),
                "drift_passes": drift_passes,
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
