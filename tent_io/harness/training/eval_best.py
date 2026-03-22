#!/usr/bin/env python3
"""Evaluate the current best unified Phase-1 checkpoint deterministically."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

TOKEN_RE = re.compile(r"[a-z0-9_]+")
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

MMLU_LABELS = ["A", "B", "C", "D"]
MMLU_TO_IDX = {v: i for i, v in enumerate(MMLU_LABELS)}
OPS = ["add", "sub", "mul", "div", "fallback"]
OP_TO_IDX = {v: i for i, v in enumerate(OPS)}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def vectorize_questions(rows: list[dict[str, Any]], vocab: dict[str, int]) -> np.ndarray:
    x = np.zeros((len(rows), len(vocab)), dtype=np.float32)
    for i, row in enumerate(rows):
        for tok in tokenize(row.get("question", "")):
            idx = vocab.get(tok)
            if idx is not None:
                x[i, idx] += 1.0
        norm = np.linalg.norm(x[i], ord=2)
        if norm > 0:
            x[i] /= norm
    return x


def infer_op_label(question: str) -> int:
    q = question.lower()
    if any(k in q for k in ("times", "product", "multiply")):
        return OP_TO_IDX["mul"]
    if any(k in q for k in ("each", "per", "equally", "divide", "shared")):
        return OP_TO_IDX["div"]
    if any(k in q for k in ("left", "remain", "after", "difference")):
        return OP_TO_IDX["sub"]
    if any(k in q for k in ("total", "sum", "add", "altogether", "combined")):
        return OP_TO_IDX["add"]
    return OP_TO_IDX["fallback"]


def mmlu_labels(rows: list[dict[str, Any]]) -> np.ndarray:
    y = np.zeros((len(rows),), dtype=np.int64)
    for i, row in enumerate(rows):
        y[i] = MMLU_TO_IDX[row["target"]]
    return y


def gsm_labels(rows: list[dict[str, Any]]) -> np.ndarray:
    y = np.zeros((len(rows),), dtype=np.int64)
    for i, row in enumerate(rows):
        y[i] = infer_op_label(row.get("question", ""))
    return y


def accuracy(logits: np.ndarray, y: np.ndarray) -> float:
    if len(y) == 0:
        return 0.0
    return float((np.argmax(logits, axis=1) == y).mean())


def normalize_number(s: str) -> str:
    m = NUM_RE.findall(str(s).replace(",", ""))
    return m[-1] if m else str(s).strip()


def execute_op(op_idx: int, question: str) -> str:
    nums = [float(n) for n in NUM_RE.findall(question.replace(",", ""))]
    if not nums:
        return "NULL"
    if op_idx == OP_TO_IDX["mul"] and len(nums) >= 2:
        return str(int(round(nums[0] * nums[1])))
    if op_idx == OP_TO_IDX["div"] and len(nums) >= 2 and nums[1] != 0:
        return str(int(round(nums[0] / nums[1])))
    if op_idx == OP_TO_IDX["sub"] and len(nums) >= 2:
        return str(int(round(nums[0] - sum(nums[1:]))))
    if op_idx == OP_TO_IDX["add"] and len(nums) >= 2:
        return str(int(round(sum(nums))))
    return str(int(round(nums[-1])))


def gsm_answer_accuracy(op_logits: np.ndarray, rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    pred_ops = np.argmax(op_logits, axis=1)
    correct = 0
    for op, row in zip(pred_ops, rows):
        pred = normalize_number(execute_op(int(op), row.get("question", "")))
        gold = normalize_number(row.get("target", ""))
        if pred == gold:
            correct += 1
    return correct / len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate best checkpoint")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/training"),
    )
    parser.add_argument(
        "--best-link",
        choices=["best_mmlu", "best_gsm_answer", "best_gsm_op"],
        default="best_mmlu",
    )
    parser.add_argument(
        "--mmlu-test-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/mmlu_test.jsonl"),
    )
    parser.add_argument(
        "--gsm8k-test-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/gsm8k_test.jsonl"),
    )
    args = parser.parse_args()

    run_dir = args.reports_dir / args.best_link
    if not run_dir.exists():
        raise SystemExit(
            f"Best link not found: {run_dir}. Run compare_runs.py --update-best-links first."
        )

    resolved_run_dir = run_dir.resolve()
    with (resolved_run_dir / "vocab.json").open("r", encoding="utf-8") as f:
        vocab = json.load(f)
    weights = np.load(resolved_run_dir / "model_weights.npz")

    w_shared = weights["w_shared"]
    b_shared = weights["b_shared"]
    w_mmlu = weights["w_mmlu"]
    b_mmlu = weights["b_mmlu"]
    w_gsm = weights["w_gsm"]
    b_gsm = weights["b_gsm"]

    mmlu_test = read_jsonl(args.mmlu_test_jsonl)
    x_mmlu_test = vectorize_questions(mmlu_test, vocab) if mmlu_test else np.zeros((0, len(vocab)), dtype=np.float32)
    y_mmlu_test = mmlu_labels(mmlu_test) if mmlu_test else np.zeros((0,), dtype=np.int64)

    gsm_test = read_jsonl(args.gsm8k_test_jsonl)
    x_gsm_test = vectorize_questions(gsm_test, vocab) if gsm_test else np.zeros((0, len(vocab)), dtype=np.float32)
    y_gsm_test = gsm_labels(gsm_test) if gsm_test else np.zeros((0,), dtype=np.int64)

    mmlu_logits = np.tanh(x_mmlu_test @ w_shared + b_shared) @ w_mmlu + b_mmlu if len(x_mmlu_test) else np.zeros((0, 4), dtype=np.float32)
    gsm_logits = np.tanh(x_gsm_test @ w_shared + b_shared) @ w_gsm + b_gsm if len(x_gsm_test) else np.zeros((0, len(OPS)), dtype=np.float32)

    out = {
        "checkpoint": str(resolved_run_dir),
        "best_link": args.best_link,
        "mmlu_test_rows": len(mmlu_test),
        "mmlu_test_acc": accuracy(mmlu_logits, y_mmlu_test),
        "gsm8k_test_rows": len(gsm_test),
        "gsm8k_op_test_acc": accuracy(gsm_logits, y_gsm_test) if len(gsm_test) else 0.0,
        "gsm8k_answer_test_acc": gsm_answer_accuracy(gsm_logits, gsm_test) if len(gsm_test) else 0.0,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
