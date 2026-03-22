#!/usr/bin/env python3
"""Evaluate a lightweight arithmetic heuristic on normalized GSM8K JSONL."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def extract_numbers(text: str) -> list[float]:
    return [float(x) for x in NUM_RE.findall(text.replace(",", ""))]


def predict(question: str) -> str:
    q = question.lower()
    nums = extract_numbers(q)
    if not nums:
        return "NULL"

    if any(k in q for k in ("times", "product", "multiply")) and len(nums) >= 2:
        return str(int(round(nums[0] * nums[1])))
    if any(k in q for k in ("each", "per", "equally", "divide", "shared")) and len(nums) >= 2 and nums[1] != 0:
        return str(int(round(nums[0] / nums[1])))
    if any(k in q for k in ("left", "remain", "after", "difference")) and len(nums) >= 2:
        return str(int(round(nums[0] - sum(nums[1:]))))
    if any(k in q for k in ("total", "sum", "add", "altogether", "combined")) and len(nums) >= 2:
        return str(int(round(sum(nums))))
    return str(int(round(nums[-1])))


def normalize(s: str) -> str:
    s = s.strip().replace(",", "")
    m = NUM_RE.findall(s)
    if not m:
        return s
    return m[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate heuristic GSM8K solver")
    parser.add_argument(
        "--gsm8k-test-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/gsm8k_test.jsonl"),
    )
    args = parser.parse_args()

    if not args.gsm8k_test_jsonl.exists():
        print(
            json.dumps(
                {
                    "rows": 0,
                    "accuracy": 0.0,
                    "note": "gsm8k_test.jsonl not found; run prepare_training_corpora.py with --gsm8k-dir or --download-gsm8k",
                },
                indent=2,
            )
        )
        return 0

    rows = read_jsonl(args.gsm8k_test_jsonl)
    if not rows:
        print(json.dumps({"rows": 0, "accuracy": 0.0, "note": "empty dataset"}, indent=2))
        return 0

    correct = 0
    for row in rows:
        pred = normalize(predict(row["question"]))
        gold = normalize(row["target"])
        if pred == gold:
            correct += 1

    acc = correct / len(rows)
    print(json.dumps({"rows": len(rows), "correct": correct, "accuracy": acc}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
