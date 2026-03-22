#!/usr/bin/env python3
"""Train a lightweight NumPy baseline on normalized MMLU JSONL.

This is a practical local baseline to start LLT iteration without external
framework dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

TOKEN_RE = re.compile(r"[a-z0-9_]+")
LABELS = ["A", "B", "C", "D"]
LABEL_TO_IDX = {label: i for i, label in enumerate(LABELS)}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def build_vocab(rows: list[dict[str, Any]], max_vocab: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for tok in tokenize(row["question"]):
            counts[tok] = counts.get(tok, 0) + 1
    sorted_tokens = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:max_vocab]
    return {tok: i for i, (tok, _) in enumerate(sorted_tokens)}


def vectorize(rows: list[dict[str, Any]], vocab: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    x = np.zeros((len(rows), len(vocab)), dtype=np.float32)
    y = np.zeros((len(rows),), dtype=np.int64)
    for i, row in enumerate(rows):
        for tok in tokenize(row["question"]):
            idx = vocab.get(tok)
            if idx is not None:
                x[i, idx] += 1.0
        x[i] /= max(1.0, np.linalg.norm(x[i], ord=2))
        y[i] = LABEL_TO_IDX[row["target"]]
    return x, y


def softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(z)
    return exp / exp.sum(axis=1, keepdims=True)


def accuracy(logits: np.ndarray, y: np.ndarray) -> float:
    pred = np.argmax(logits, axis=1)
    return float((pred == y).mean())


def main() -> int:
    parser = argparse.ArgumentParser(description="Train local NumPy MMLU baseline")
    parser.add_argument(
        "--train-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/mmlu_train.jsonl"),
    )
    parser.add_argument(
        "--test-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/mmlu_test.jsonl"),
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--lr", type=float, default=0.3)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--max-vocab", type=int, default=8000)
    args = parser.parse_args()

    train_rows = read_jsonl(args.train_jsonl)
    test_rows = read_jsonl(args.test_jsonl)
    vocab = build_vocab(train_rows, max_vocab=args.max_vocab)
    x_train, y_train = vectorize(train_rows, vocab)
    x_test, y_test = vectorize(test_rows, vocab)

    rng = np.random.default_rng(7)
    w = rng.normal(scale=0.01, size=(x_train.shape[1], len(LABELS))).astype(np.float32)
    b = np.zeros((1, len(LABELS)), dtype=np.float32)

    for epoch in range(1, args.epochs + 1):
        logits = x_train @ w + b
        probs = softmax(logits)
        onehot = np.eye(len(LABELS), dtype=np.float32)[y_train]

        grad_logits = (probs - onehot) / len(x_train)
        grad_w = x_train.T @ grad_logits + args.l2 * w
        grad_b = grad_logits.sum(axis=0, keepdims=True)

        w -= args.lr * grad_w
        b -= args.lr * grad_b

        if epoch == 1 or epoch % 5 == 0 or epoch == args.epochs:
            train_acc = accuracy(logits, y_train)
            test_acc = accuracy(x_test @ w + b, y_test)
            print(f"epoch={epoch:02d} train_acc={train_acc:.4f} test_acc={test_acc:.4f}")

    final_test_acc = accuracy(x_test @ w + b, y_test)
    print(
        json.dumps(
            {
                "train_rows": len(train_rows),
                "test_rows": len(test_rows),
                "vocab_size": len(vocab),
                "final_test_acc": final_test_acc,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
