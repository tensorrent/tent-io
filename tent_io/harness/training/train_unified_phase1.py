#!/usr/bin/env python3
"""Unified Phase-1 trainer: shared encoder, MMLU + GSM8K heads.

This script is intentionally lightweight (NumPy only) so it can run in local
environments without a deep learning framework while preserving a multi-task
training loop.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from datetime import datetime, timezone

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


def load_merkle_memory_rows(merkle_map_path: Path, max_events: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not merkle_map_path.exists():
        return [], []
    try:
        data = json.loads(merkle_map_path.read_text(encoding="utf-8"))
    except Exception:
        return [], []

    synthesis = data.get("synthesis", {})
    if not isinstance(synthesis, dict):
        return [], []
    instructions = synthesis.get("instructions", [])
    if not isinstance(instructions, list):
        return [], []

    mmlu_rows: list[dict[str, Any]] = []
    gsm_rows: list[dict[str, Any]] = []

    for inst in instructions:
        if not isinstance(inst, dict):
            continue
        if inst.get("instruction") != "replay_pin_event":
            continue
        if inst.get("message_type") != "note_on":
            continue
        prime_n = int(inst.get("prime_n", 2))
        cylinder_pin = int(inst.get("cylinder_pin", 0))
        path_text = str(inst.get("path", ""))
        xy = inst.get("ulam_xy", [0, 0])
        x = int(xy[0]) if isinstance(xy, list) and len(xy) > 0 else 0
        y = int(xy[1]) if isinstance(xy, list) and len(xy) > 1 else 0

        # MMLU replay sample (deterministic label derived from prime/pin/x/y).
        mmlu_target = MMLU_LABELS[(prime_n + cylinder_pin + abs(x) + abs(y)) % len(MMLU_LABELS)]
        mmlu_rows.append(
            {
                "question": (
                    f"memory replay mmlu from persistent merkle map for path {path_text} "
                    f"with prime {prime_n} pin {cylinder_pin} and ulam {x} {y}; "
                    f"select deterministic option by replay rule"
                ),
                "target": mmlu_target,
            }
        )

        # GSM replay sample (deterministic add operation anchor).
        gsm_answer = str(prime_n + cylinder_pin)
        gsm_rows.append(
            {
                "question": (
                    f"memory replay arithmetic total from persistent merkle pin: "
                    f"prime {prime_n} add pin {cylinder_pin} for path {path_text}"
                ),
                "target": gsm_answer,
            }
        )
        if len(mmlu_rows) >= max_events and len(gsm_rows) >= max_events:
            break
    return mmlu_rows, gsm_rows


def build_vocab(rows: list[dict[str, Any]], max_vocab: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for tok in tokenize(row.get("question", "")):
            counts[tok] = counts.get(tok, 0) + 1
    pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:max_vocab]
    return {tok: i for i, (tok, _) in enumerate(pairs)}


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


def softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def mmlu_labels(rows: list[dict[str, Any]]) -> np.ndarray:
    y = np.zeros((len(rows),), dtype=np.int64)
    for i, row in enumerate(rows):
        y[i] = MMLU_TO_IDX[row["target"]]
    return y


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
    parser = argparse.ArgumentParser(description="Unified MMLU+GSM8K Phase-1 trainer")
    parser.add_argument(
        "--mmlu-train-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/mmlu_train.jsonl"),
    )
    parser.add_argument(
        "--mmlu-test-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/mmlu_test.jsonl"),
    )
    parser.add_argument(
        "--gsm8k-train-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/gsm8k_train.jsonl"),
    )
    parser.add_argument(
        "--gsm8k-test-jsonl",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/fixtures/training/gsm8k_test.jsonl"),
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--max-vocab", type=int, default=10000)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument(
        "--disable-merkle-memory",
        action="store_true",
        help="Disable persistent Merkle replay rows in training data.",
    )
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
        help="Directory where model/report artifacts are written.",
    )
    args = parser.parse_args()

    mmlu_train = read_jsonl(args.mmlu_train_jsonl)
    mmlu_test = read_jsonl(args.mmlu_test_jsonl)
    gsm_train = read_jsonl(args.gsm8k_train_jsonl)
    gsm_test = read_jsonl(args.gsm8k_test_jsonl)

    if not mmlu_train or not mmlu_test:
        raise SystemExit("MMLU corpora not found. Run prepare_training_corpora.py first.")

    mmlu_merkle_rows: list[dict[str, Any]] = []
    gsm_merkle_rows: list[dict[str, Any]] = []
    if not args.disable_merkle_memory:
        mmlu_merkle_rows, gsm_merkle_rows = load_merkle_memory_rows(args.merkle_map, args.merkle_max_events)
        mmlu_train.extend(mmlu_merkle_rows)
        gsm_train.extend(gsm_merkle_rows)

    vocab = build_vocab(mmlu_train + gsm_train, max_vocab=args.max_vocab)
    x_mmlu_train = vectorize_questions(mmlu_train, vocab)
    x_mmlu_test = vectorize_questions(mmlu_test, vocab)
    y_mmlu_train = mmlu_labels(mmlu_train)
    y_mmlu_test = mmlu_labels(mmlu_test)

    x_gsm_train = vectorize_questions(gsm_train, vocab) if gsm_train else np.zeros((0, len(vocab)), dtype=np.float32)
    x_gsm_test = vectorize_questions(gsm_test, vocab) if gsm_test else np.zeros((0, len(vocab)), dtype=np.float32)
    y_gsm_train = gsm_labels(gsm_train) if gsm_train else np.zeros((0,), dtype=np.int64)
    y_gsm_test = gsm_labels(gsm_test) if gsm_test else np.zeros((0,), dtype=np.int64)

    rng = np.random.default_rng(42)
    w_shared = rng.normal(scale=0.03, size=(len(vocab), args.hidden_dim)).astype(np.float32)
    b_shared = np.zeros((1, args.hidden_dim), dtype=np.float32)
    w_mmlu = rng.normal(scale=0.03, size=(args.hidden_dim, 4)).astype(np.float32)
    b_mmlu = np.zeros((1, 4), dtype=np.float32)
    w_gsm = rng.normal(scale=0.03, size=(args.hidden_dim, len(OPS))).astype(np.float32)
    b_gsm = np.zeros((1, len(OPS)), dtype=np.float32)
    epoch_logs: list[dict[str, Any]] = []

    for epoch in range(1, args.epochs + 1):
        # MMLU step
        h_mmlu = np.tanh(x_mmlu_train @ w_shared + b_shared)
        logits_mmlu = h_mmlu @ w_mmlu + b_mmlu
        probs_mmlu = softmax(logits_mmlu)
        onehot_mmlu = np.eye(4, dtype=np.float32)[y_mmlu_train]
        dlogits_mmlu = (probs_mmlu - onehot_mmlu) / len(x_mmlu_train)
        dw_mmlu = h_mmlu.T @ dlogits_mmlu + args.l2 * w_mmlu
        db_mmlu = dlogits_mmlu.sum(axis=0, keepdims=True)
        dh_mmlu = dlogits_mmlu @ w_mmlu.T
        dz_mmlu = dh_mmlu * (1 - h_mmlu * h_mmlu)
        dw_shared_mmlu = x_mmlu_train.T @ dz_mmlu
        db_shared_mmlu = dz_mmlu.sum(axis=0, keepdims=True)

        # GSM step (optional)
        if len(x_gsm_train) > 0:
            h_gsm = np.tanh(x_gsm_train @ w_shared + b_shared)
            logits_gsm = h_gsm @ w_gsm + b_gsm
            probs_gsm = softmax(logits_gsm)
            onehot_gsm = np.eye(len(OPS), dtype=np.float32)[y_gsm_train]
            dlogits_gsm = (probs_gsm - onehot_gsm) / len(x_gsm_train)
            dw_gsm = h_gsm.T @ dlogits_gsm + args.l2 * w_gsm
            db_gsm = dlogits_gsm.sum(axis=0, keepdims=True)
            dh_gsm = dlogits_gsm @ w_gsm.T
            dz_gsm = dh_gsm * (1 - h_gsm * h_gsm)
            dw_shared_gsm = x_gsm_train.T @ dz_gsm
            db_shared_gsm = dz_gsm.sum(axis=0, keepdims=True)
        else:
            dw_gsm = np.zeros_like(w_gsm)
            db_gsm = np.zeros_like(b_gsm)
            dw_shared_gsm = np.zeros_like(w_shared)
            db_shared_gsm = np.zeros_like(b_shared)

        # Joint update
        w_shared -= args.lr * ((dw_shared_mmlu + dw_shared_gsm) + args.l2 * w_shared)
        b_shared -= args.lr * (db_shared_mmlu + db_shared_gsm)
        w_mmlu -= args.lr * dw_mmlu
        b_mmlu -= args.lr * db_mmlu
        w_gsm -= args.lr * dw_gsm
        b_gsm -= args.lr * db_gsm

        if epoch == 1 or epoch % 5 == 0 or epoch == args.epochs:
            mmlu_train_acc = accuracy(logits_mmlu, y_mmlu_train)
            mmlu_test_acc = accuracy(np.tanh(x_mmlu_test @ w_shared + b_shared) @ w_mmlu + b_mmlu, y_mmlu_test)
            log = {
                "epoch": epoch,
                "mmlu_train_acc": mmlu_train_acc,
                "mmlu_test_acc": mmlu_test_acc,
            }
            if len(x_gsm_train) > 0:
                gsm_train_logits = np.tanh(x_gsm_train @ w_shared + b_shared) @ w_gsm + b_gsm
                gsm_test_logits = np.tanh(x_gsm_test @ w_shared + b_shared) @ w_gsm + b_gsm
                log["gsm_op_train_acc"] = accuracy(gsm_train_logits, y_gsm_train)
                log["gsm_op_test_acc"] = accuracy(gsm_test_logits, y_gsm_test)
                log["gsm_answer_test_acc"] = gsm_answer_accuracy(gsm_test_logits, gsm_test)
            print(json.dumps(log))
            epoch_logs.append(log)

    final = {
        "mmlu_train_rows": len(mmlu_train),
        "mmlu_test_rows": len(mmlu_test),
        "gsm_train_rows": len(gsm_train),
        "gsm_test_rows": len(gsm_test),
        "rows_merkle_replay_mmlu": len(mmlu_merkle_rows),
        "rows_merkle_replay_gsm": len(gsm_merkle_rows),
        "merkle_memory_enabled": not args.disable_merkle_memory,
        "merkle_map": str(args.merkle_map),
        "vocab_size": len(vocab),
    }
    if len(x_gsm_train) > 0:
        final["final_gsm_answer_test_acc"] = gsm_answer_accuracy(
            np.tanh(x_gsm_test @ w_shared + b_shared) @ w_gsm + b_gsm,
            gsm_test,
        )
    final["final_mmlu_test_acc"] = accuracy(
        np.tanh(x_mmlu_test @ w_shared + b_shared) @ w_mmlu + b_mmlu,
        y_mmlu_test,
    )

    run_started = datetime.now(timezone.utc)
    run_id = run_started.strftime("%Y%m%dT%H%M%S") + f"{run_started.microsecond // 1000:03d}Z"
    run_dir = args.save_dir / f"unified_phase1_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        run_dir / "model_weights.npz",
        w_shared=w_shared,
        b_shared=b_shared,
        w_mmlu=w_mmlu,
        b_mmlu=b_mmlu,
        w_gsm=w_gsm,
        b_gsm=b_gsm,
    )
    with (run_dir / "vocab.json").open("w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=True)
    report = {
        "run_id": run_id,
        "config": {
            "epochs": args.epochs,
            "max_vocab": args.max_vocab,
            "hidden_dim": args.hidden_dim,
            "lr": args.lr,
            "l2": args.l2,
            "disable_merkle_memory": args.disable_merkle_memory,
            "merkle_map": str(args.merkle_map),
            "merkle_max_events": args.merkle_max_events,
        },
        "inputs": {
            "mmlu_train_jsonl": str(args.mmlu_train_jsonl),
            "mmlu_test_jsonl": str(args.mmlu_test_jsonl),
            "gsm8k_train_jsonl": str(args.gsm8k_train_jsonl),
            "gsm8k_test_jsonl": str(args.gsm8k_test_jsonl),
        },
        "epoch_logs": epoch_logs,
        "final_metrics": final,
    }
    with (run_dir / "report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=True, indent=2)
    final["artifacts_dir"] = str(run_dir)
    print(json.dumps(final, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
