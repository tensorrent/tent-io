#!/usr/bin/env python3
"""
Phase B Option 2 — Pull 100 GPQA Diamond questions from HuggingFace.
Output: benchmark_questions_gpqa_100.json (spec-compliant format).

Requires: pip install datasets
"""

import json
import random
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "benchmark_questions_gpqa_100.json"


def main() -> int:
    try:
        from datasets import load_dataset
    except ImportError:
        print("pip install datasets", file=sys.stderr)
        return 1

    ds = load_dataset("Idavidrein/gpqa", "gpqa_diamond", split="train", trust_remote_code=True)
    random.seed(42)
    n = min(100, len(ds))
    indices = random.sample(range(len(ds)), n)

    questions = []
    for idx in indices:
        item = ds[idx]
        correct_text = item["Correct Answer"]
        incorrect = [
            item["Incorrect Answer 1"],
            item["Incorrect Answer 2"],
            item["Incorrect Answer 3"],
        ]
        options_raw = [correct_text] + incorrect
        combined = list(zip(["A", "B", "C", "D"], options_raw))
        random.seed(42 + idx)
        random.shuffle(combined)
        options = [f"{l}) {t}" for l, t in combined]
        expected = next(l for l, t in combined if t == correct_text)
        questions.append({
            "id": f"gpqa-diamond-{idx:04d}",
            "category": item.get("subdomain", "unknown"),
            "question": item["Question"],
            "options": options,
            "expected_answer": expected,
            "source": "Idavidrein/gpqa gpqa_diamond",
            "source_index": idx,
        })

    with open(OUTPUT, "w") as f:
        json.dump(questions, f, indent=2)
    print(f"Saved {len(questions)} GPQA Diamond questions to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
