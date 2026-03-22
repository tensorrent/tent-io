#!/usr/bin/env python3
"""Train a deterministic liquid language model on MMLU-style JSONL."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
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
    if isinstance(choices, list):
        joined = " ".join(str(c) for c in choices)
    else:
        joined = ""
    return f"{question} {joined}".strip()


def load_merkle_rows(path: Path, max_events: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    synthesis = data.get("synthesis", {})
    if not isinstance(synthesis, dict):
        return []
    instructions = synthesis.get("instructions", [])
    if not isinstance(instructions, list):
        return []
    out: list[dict[str, Any]] = []
    for inst in instructions:
        if not isinstance(inst, dict):
            continue
        if inst.get("instruction") != "replay_pin_event":
            continue
        if inst.get("message_type") != "note_on":
            continue
        prime_n = int(inst.get("prime_n", 2))
        pin = int(inst.get("cylinder_pin", 0))
        xy = inst.get("ulam_xy", [0, 0])
        x = int(xy[0]) if isinstance(xy, list) and len(xy) > 0 else 0
        y = int(xy[1]) if isinstance(xy, list) and len(xy) > 1 else 0
        path_text = str(inst.get("path", ""))
        ans_idx = (prime_n + pin + abs(x) + abs(y)) % 4
        # Deterministic 4-choice synthetic prompt from persistent memory.
        out.append(
            {
                "question": (
                    f"Persistent Merkle replay for path {path_text} with prime {prime_n}, pin {pin}, "
                    f"and ulam coordinates {x} {y}. Select the deterministic replay channel."
                ),
                "choices": ["channel alpha", "channel beta", "channel gamma", "channel delta"],
                "target": LABELS[ans_idx],
            }
        )
        if len(out) >= max_events:
            break
    return out


def build_vocab(rows: list[dict[str, Any]], max_vocab: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        for t in tok(row_text(r)):
            counts[t] = counts.get(t, 0) + 1
    pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:max_vocab]
    return {t: i for i, (t, _) in enumerate(pairs)}


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


def softmax(z: np.ndarray) -> np.ndarray:
    z2 = z - z.max(axis=1, keepdims=True)
    e = np.exp(z2)
    return e / e.sum(axis=1, keepdims=True)


def acc(logits: np.ndarray, y: np.ndarray) -> float:
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


class LiquidMLP:
    """Compact liquid-inspired classifier with deterministic updates."""

    def __init__(self, d_in: int, d_hidden: int, d_out: int, seed: int = 7) -> None:
        rng = np.random.default_rng(seed)
        self.w_in = rng.normal(scale=0.03, size=(d_in, d_hidden)).astype(np.float32)
        self.b_in = np.zeros((1, d_hidden), dtype=np.float32)
        self.w_liq = rng.normal(scale=0.01, size=(d_hidden, d_hidden)).astype(np.float32)
        self.w_out = rng.normal(scale=0.03, size=(d_hidden, d_out)).astype(np.float32)
        self.b_out = np.zeros((1, d_out), dtype=np.float32)

    def forward(self, x: np.ndarray, dt: float = 0.15) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        h0 = np.tanh(x @ self.w_in + self.b_in)
        # Liquid step: h1 = h0 + dt * tanh(h0 @ W_liq)
        liq = np.tanh(h0 @ self.w_liq)
        h1 = h0 + dt * liq
        logits = h1 @ self.w_out + self.b_out
        return h0, h1, logits


def main() -> int:
    parser = argparse.ArgumentParser(description="Train liquid language model on MMLU JSONL")
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
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--lr", type=float, default=0.10)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--max-vocab", type=int, default=10000)
    parser.add_argument("--hidden-dim", type=int, default=96)
    parser.add_argument("--dt", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-train", type=int, default=0, help="Optional cap for train rows (0 = all)")
    parser.add_argument("--max-test", type=int, default=0, help="Optional cap for test rows (0 = all)")
    parser.add_argument("--disable-merkle-memory", action="store_true")
    parser.add_argument("--disable-conversational-logic", action="store_true")
    parser.add_argument("--conversation-train-rows", type=int, default=256)
    parser.add_argument("--conversation-test-rows", type=int, default=128)
    parser.add_argument("--conversation-seed", type=int, default=17)
    parser.add_argument(
        "--merkle-map",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_merkle_tensor_scroll.current.json"),
    )
    parser.add_argument("--merkle-max-events", type=int, default=128)
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/training"),
    )
    args = parser.parse_args()

    train_rows = read_jsonl(args.train_jsonl)
    test_rows = read_jsonl(args.test_jsonl)
    for r in train_rows:
        r.setdefault("source", "mmlu")
    for r in test_rows:
        r.setdefault("source", "mmlu")
    if args.max_train > 0:
        train_rows = train_rows[: args.max_train]
    if args.max_test > 0:
        test_rows = test_rows[: args.max_test]
    if not train_rows or not test_rows:
        raise SystemExit("MMLU corpora not found. Run prepare_training_corpora.py first.")

    conversational_train_rows: list[dict[str, Any]] = []
    conversational_test_rows: list[dict[str, Any]] = []
    if not args.disable_conversational_logic:
        conversational_train_rows = build_conversational_logic_rows(
            count=args.conversation_train_rows,
            seed=args.conversation_seed,
            split="train",
        )
        conversational_test_rows = build_conversational_logic_rows(
            count=args.conversation_test_rows,
            seed=args.conversation_seed,
            split="test",
        )
        train_rows.extend(conversational_train_rows)
        test_rows.extend(conversational_test_rows)

    merkle_rows: list[dict[str, Any]] = []
    if not args.disable_merkle_memory:
        merkle_rows = load_merkle_rows(args.merkle_map, args.merkle_max_events)
        for r in merkle_rows:
            r.setdefault("source", "merkle_replay")
        train_rows.extend(merkle_rows)

    vocab = build_vocab(train_rows, args.max_vocab)
    x_train, y_train = vectorize(train_rows, vocab)
    x_test, y_test = vectorize(test_rows, vocab)

    model = LiquidMLP(d_in=len(vocab), d_hidden=args.hidden_dim, d_out=4, seed=args.seed)
    logs: list[dict[str, Any]] = []

    for epoch in range(1, args.epochs + 1):
        h0, h1, logits = model.forward(x_train, dt=args.dt)
        p = softmax(logits)
        oh = np.eye(4, dtype=np.float32)[y_train]
        dlogits = (p - oh) / len(x_train)

        # output gradients
        dw_out = h1.T @ dlogits + args.l2 * model.w_out
        db_out = dlogits.sum(axis=0, keepdims=True)
        dh1 = dlogits @ model.w_out.T

        # liquid gradients
        liq_pre = h0 @ model.w_liq
        liq = np.tanh(liq_pre)
        dliq = dh1 * args.dt
        dliq_pre = dliq * (1 - liq * liq)
        dw_liq = h0.T @ dliq_pre + args.l2 * model.w_liq
        dh0 = dh1 + dliq_pre @ model.w_liq.T

        # input gradients
        dz0 = dh0 * (1 - h0 * h0)
        dw_in = x_train.T @ dz0 + args.l2 * model.w_in
        db_in = dz0.sum(axis=0, keepdims=True)

        model.w_out -= args.lr * dw_out
        model.b_out -= args.lr * db_out
        model.w_liq -= args.lr * dw_liq
        model.w_in -= args.lr * dw_in
        model.b_in -= args.lr * db_in

        if epoch == 1 or epoch % 2 == 0 or epoch == args.epochs:
            _, _, tlogits = model.forward(x_test, dt=args.dt)
            log = {
                "epoch": epoch,
                "train_acc": acc(logits, y_train),
                "test_acc": acc(tlogits, y_test),
            }
            logs.append(log)
            print(json.dumps(log))

    run_started = datetime.now(timezone.utc)
    run_id = run_started.strftime("%Y%m%dT%H%M%S") + f"{run_started.microsecond // 1000:03d}Z"
    run_dir = args.save_dir / f"liquid_llt_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        run_dir / "model_weights.npz",
        w_in=model.w_in,
        b_in=model.b_in,
        w_liq=model.w_liq,
        w_out=model.w_out,
        b_out=model.b_out,
    )
    with (run_dir / "vocab.json").open("w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=True)

    _, _, logits_test = model.forward(x_test, dt=args.dt)
    final = {
        "run_id": run_id,
        "rows_train": len(train_rows),
        "rows_test": len(test_rows),
        "rows_conversational_logic_train": len(conversational_train_rows),
        "rows_conversational_logic_test": len(conversational_test_rows),
        "conversational_logic_enabled": not args.disable_conversational_logic,
        "rows_merkle_replay": len(merkle_rows),
        "merkle_memory_enabled": not args.disable_merkle_memory,
        "merkle_map": str(args.merkle_map),
        "vocab_size": len(vocab),
        "hidden_dim": args.hidden_dim,
        "final_test_acc": acc(logits_test, y_test),
        "final_mmlu_test_acc": subset_acc(logits_test, y_test, test_rows, "mmlu"),
        "final_conversational_logic_test_acc": subset_acc(
            logits_test, y_test, test_rows, "conversational_logic"
        ),
        "artifacts_dir": str(run_dir),
    }
    with (run_dir / "report.json").open("w", encoding="utf-8") as f:
        json.dump({"config": vars(args), "epoch_logs": logs, "final_metrics": final}, f, indent=2, ensure_ascii=True, default=str)

    print(json.dumps(final, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
