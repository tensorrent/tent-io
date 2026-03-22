#!/usr/bin/env python3
"""
Phase B Option 1 — Pull 100 MMLU-Pro questions from HuggingFace (TIGER-Lab/MMLU-Pro).
Output: benchmark_questions_100.json (spec-compliant format).

Requires: pip install datasets
"""

import json
import random
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "benchmark_questions_100.json"


def main() -> int:
    try:
        from datasets import load_dataset
    except ImportError:
        print("pip install datasets", file=sys.stderr)
        return 1

    ds = load_dataset("TIGER-Lab/MMLU-Pro", split="test", trust_remote_code=True)
    random.seed(42)
    n = min(100, len(ds))
    indices = random.sample(range(len(ds)), n)

    questions = []
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, idx in enumerate(indices):
        item = ds[idx]
        opts = item.get("options", [])
        options = [f"{letters[j]}) {o}" for j, o in enumerate(opts)]
        # expected_answer: letter from dataset (often 0-based index → A/B/C/D)
        ans = item.get("answer", 0)
        if isinstance(ans, int):
            expected = letters[ans] if ans < len(letters) else "A"
        else:
            expected = str(ans).strip().upper()[:1] or "A"
        questions.append({
            "id": f"mmlu-pro-{idx:05d}",
            "category": item.get("category", "unknown"),
            "question": item.get("question", ""),
            "options": options,
            "expected_answer": expected,
            "source": "TIGER-Lab/MMLU-Pro",
            "source_index": idx,
        })

    with open(OUTPUT, "w") as f:
        json.dump(questions, f, indent=2)
    print(f"Saved {len(questions)} questions to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
