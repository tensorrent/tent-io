#!/usr/bin/env python3
"""Trim LLT drift NDJSON history to the last N rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Trim LLT drift history NDJSON to last N rows")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/llt_drift_history.ndjson"),
        help="NDJSON history file path.",
    )
    parser.add_argument(
        "--keep-last",
        type=int,
        default=200,
        help="Keep only the last N rows (default: 200).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing changes.",
    )
    args = parser.parse_args()

    if args.keep_last < 1:
        raise SystemExit("--keep-last must be >= 1")

    if not args.path.exists():
        print(
            json.dumps(
                {
                    "status": "ok",
                    "path": str(args.path),
                    "rows_before": 0,
                    "rows_after": 0,
                    "trimmed": 0,
                    "note": "file_missing_noop",
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    with args.path.open("r", encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]

    before = len(lines)
    kept = lines[-args.keep_last :] if before > args.keep_last else lines
    after = len(kept)
    trimmed = before - after

    if not args.dry_run and trimmed > 0:
        args.path.parent.mkdir(parents=True, exist_ok=True)
        with args.path.open("w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n")

    print(
        json.dumps(
            {
                "status": "ok",
                "path": str(args.path),
                "rows_before": before,
                "rows_after": after,
                "trimmed": trimmed,
                "dry_run": args.dry_run,
                "keep_last": args.keep_last,
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
