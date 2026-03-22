#!/usr/bin/env python3
"""Deterministically evaluate best liquid language model checkpoint."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

try:
    from tent_io.harness.training.conversational_logic_rows import build_conversational_logic_rows
except ModuleNotFoundError:
    # Support direct script execution from repository root.
    from conversational_logic_rows import build_conversational_logic_rows

TOKEN_RE = re.compile(r"[a-z0-9_]+")
LABELS = ["A", "B", "C", "D"]
LABEL_TO_IDX = {v: i for i, v in enumerate(LABELS)}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def tok(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def row_text(row: dict[str, Any]) -> str:
    question = str(row.get("question", ""))
    choices = row.get("choices", [])
    joined = " ".join(str(c) for c in choices) if isinstance(choices, list) else ""
    return f"{question} {joined}".strip()


def vectorize(rows: list[dict[str, Any]], vocab: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    x = np.zeros((len(rows), len(vocab)), dtype=np.float32)
    y = np.zeros((len(rows),), dtype=np.int64)
    for i, r in enumerate(rows):
        for t in tok(row_text(r)):
            j = vocab.get(t)
            if j is not None:
                x[i, j] += 1.0
        n = np.linalg.norm(x[i], ord=2)
        if n > 0:
            x[i] /= n
        y[i] = LABEL_TO_IDX.get(str(r.get("target", "A")), 0)
    return x, y


def acc(logits: np.ndarray, y: np.ndarray) -> float:
    if len(y) == 0:
        return 0.0
    return float((np.argmax(logits, axis=1) == y).mean())


def subset_acc(logits: np.ndarray, y: np.ndarray, rows: list[dict[str, Any]], source: str) -> float | None:
    if source == "mmlu":
        idx = [
            i
            for i, r in enumerate(rows)
            if str(r.get("source", "mmlu")) != "conversational_logic"
        ]
    else:
        idx = [i for i, r in enumerate(rows) if str(r.get("source", "mmlu")) == source]
    if not idx:
        return None
    s = np.array(idx, dtype=np.int64)
    return acc(logits[s], y[s])


def forward(x: np.ndarray, w_in: np.ndarray, b_in: np.ndarray, w_liq: np.ndarray, w_out: np.ndarray, b_out: np.ndarray, dt: float) -> np.ndarray:
    h0 = np.tanh(x @ w_in + b_in)
    h1 = h0 + dt * np.tanh(h0 @ w_liq)
    return h1 @ w_out + b_out


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate best liquid language model checkpoint")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/training"),
    )
    parser.add_argument("--best-link", default="best_liquid_llt")
    parser.add_argument("--checkpoint-dir", type=Path, default=None, help="Optional explicit checkpoint directory.")
    parser.add_argument(
        "--test-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/mmlu_test.jsonl"),
    )
    parser.add_argument("--dt", type=float, default=0.15)
    parser.add_argument("--max-test", type=int, default=0, help="Optional cap for test rows (0 = all)")
    parser.add_argument("--disable-conversational-logic", action="store_true")
    parser.add_argument("--conversation-test-rows", type=int, default=128)
    parser.add_argument("--conversation-seed", type=int, default=17)
    args = parser.parse_args()

    run_dir = args.checkpoint_dir.resolve() if args.checkpoint_dir else (args.reports_dir / args.best_link).resolve()
    if not run_dir.exists():
        if args.checkpoint_dir:
            raise SystemExit(f"Checkpoint not found: {args.checkpoint_dir}")
        raise SystemExit(f"Best link not found: {args.reports_dir / args.best_link}")

    with (run_dir / "vocab.json").open("r", encoding="utf-8") as f:
        vocab = json.load(f)
    weights = np.load(run_dir / "model_weights.npz")
    w_in = weights["w_in"]
    b_in = weights["b_in"]
    w_liq = weights["w_liq"]
    w_out = weights["w_out"]
    b_out = weights["b_out"]

    rows = read_jsonl(args.test_jsonl)
    for r in rows:
        r.setdefault("source", "mmlu")
    if args.max_test > 0:
        rows = rows[: args.max_test]
    conversational_test_rows: list[dict[str, Any]] = []
    if not args.disable_conversational_logic:
        conversational_test_rows = build_conversational_logic_rows(
            count=args.conversation_test_rows,
            seed=args.conversation_seed,
            split="test",
        )
        rows.extend(conversational_test_rows)
    x, y = vectorize(rows, vocab)
    logits = forward(x, w_in, b_in, w_liq, w_out, b_out, dt=args.dt) if len(rows) else np.zeros((0, 4), dtype=np.float32)

    out = {
        "checkpoint": str(run_dir),
        "best_link": args.best_link,
        "rows_test": len(rows),
        "rows_conversational_logic_test": len(conversational_test_rows),
        "conversational_logic_enabled": not args.disable_conversational_logic,
        "dt": args.dt,
        "test_acc": acc(logits, y),
        "mmlu_test_acc": subset_acc(logits, y, rows, "mmlu"),
        "conversational_logic_test_acc": subset_acc(logits, y, rows, "conversational_logic"),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
