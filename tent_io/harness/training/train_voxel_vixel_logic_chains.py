#!/usr/bin/env python3
"""Train logic-chain classifiers for voxel/vixel/vexel/boxels stack.

Outputs:
- stack classifier accuracy
- step classifier accuracy
- run artifacts (weights, vocab, chain map, report)
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

TOKEN_RE = re.compile(r"[a-z0-9_]+")

STACKS = ["voxel", "vixel", "vexel", "boxels"]
STACK_TO_IDX = {s: i for i, s in enumerate(STACKS)}
STACK_ROLES: dict[str, str] = {
    "voxel": "base voxel structure",
    "vixel": "specialized bins within voxel structure",
    "vexel": "outward polymorphic pixel representation (public structure)",
    "boxels": "full avatar polymorphic structure",
}

CHAIN_STEPS: dict[str, list[str]] = {
    "voxel": ["quantize_volume", "occupancy_mark", "spatial_index", "merge_region"],
    "vixel": ["intent_bind", "field_route", "confidence_gate", "reason_emit"],
    "vexel": ["vector_encode", "edge_expand", "execution_plan", "state_commit"],
    "boxels": ["box_partition", "mesh_assign", "sparsity_balance", "consensus_pack"],
}

STACK_CUES: dict[str, list[str]] = {
    "voxel": ["volume", "gridcell", "occupancy", "octree", "spatial"],
    "vixel": ["bin", "bucket", "channel", "specialized", "routing"],
    "vexel": ["outward", "polymorphic", "public", "surface", "pixel"],
    "boxels": ["box", "mesh", "placement", "consensus", "partition"],
}

STEP_KEYWORDS: dict[str, list[str]] = {
    "voxel:quantize_volume": ["quantize", "volume", "grid", "resolution"],
    "voxel:occupancy_mark": ["occupancy", "filled", "empty", "mask"],
    "voxel:spatial_index": ["index", "octree", "coordinate", "lookup"],
    "voxel:merge_region": ["merge", "region", "adjacent", "cluster"],
    "vixel:intent_bind": ["intent", "bind", "symbol", "context"],
    "vixel:field_route": ["field", "route", "domain", "signal"],
    "vixel:confidence_gate": ["confidence", "gate", "threshold", "abstain"],
    "vixel:reason_emit": ["reason", "emit", "explain", "trace"],
    "vexel:vector_encode": ["vector", "encode", "projection", "basis"],
    "vexel:edge_expand": ["edge", "expand", "neighbors", "graph"],
    "vexel:execution_plan": ["execution", "plan", "steps", "schedule"],
    "vexel:state_commit": ["state", "commit", "checkpoint", "persist"],
    "boxels:box_partition": ["box", "partition", "tile", "segment"],
    "boxels:mesh_assign": ["mesh", "assign", "node", "placement"],
    "boxels:sparsity_balance": ["sparsity", "balance", "dense", "sparse"],
    "boxels:consensus_pack": ["consensus", "pack", "bundle", "integrity"],
}


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def infer_stack_from_path(path_text: str, prime_n: int) -> str:
    low = path_text.lower()
    for stack in STACKS:
        if stack in low:
            return stack
    return STACKS[prime_n % len(STACKS)]


def infer_step(stack: str, cylinder_pin: int) -> str:
    steps = CHAIN_STEPS[stack]
    return steps[cylinder_pin % len(steps)]


def load_merkle_memory_rows(merkle_map_path: Path, max_events: int) -> list[dict[str, str]]:
    if not merkle_map_path.exists():
        return []
    try:
        data = json.loads(merkle_map_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    synthesis = data.get("synthesis", {})
    if not isinstance(synthesis, dict):
        return []
    instructions = synthesis.get("instructions", [])
    if not isinstance(instructions, list):
        return []

    rows: list[dict[str, str]] = []
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

        stack = infer_stack_from_path(path_text, prime_n)
        step = infer_step(stack, cylinder_pin)
        key = f"{stack}:{step}"
        kws = STEP_KEYWORDS[key][:2]
        stack_kws = STACK_CUES[stack][:2]
        text = (
            f"replay persistent merkle pin stack_{stack} {stack} chain with {stack_kws[0]} {stack_kws[1]} "
            f"and {kws[0]} {kws[1]} role_{stack}_{STACK_ROLES[stack].replace(' ', '_')} "
            f"prime_{prime_n} pin_{cylinder_pin} ulam_{x}_{y} memory_reuse"
        )
        rows.append({"text": text, "stack": stack, "step": key})
        if len(rows) >= max_events:
            break
    return rows


def synthesize_dataset(samples_per_step: int, seed: int) -> tuple[list[dict[str, str]], dict[str, int]]:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, str]] = []
    step_names = []
    for stack, steps in CHAIN_STEPS.items():
        for step in steps:
            step_names.append(f"{stack}:{step}")
            for _ in range(samples_per_step):
                # Deterministic templating with stack + step cues and hard negatives.
                verb = rng.choice(["run", "apply", "execute", "compute", "trigger"])
                mod = rng.choice(["now", "for node", "for profile", "under sparse mode", "under dense mode"])
                key = f"{stack}:{step}"
                kw = rng.choice(STEP_KEYWORDS[key], size=2, replace=False)
                stack_kw = rng.choice(STACK_CUES[stack], size=2, replace=False)
                q = (
                    f"{verb} stack_{stack} {stack} chain with {stack_kw[0]} {stack_kw[1]} "
                    f"and {kw[0]} {kw[1]} role_{stack}_{STACK_ROLES[stack].replace(' ', '_')} {mod}"
                )
                # Add hard-negative distractor from another stack in some samples.
                if rng.random() < 0.35:
                    other = rng.choice([s for s in STACKS if s != stack])
                    distract = rng.choice(STACK_CUES[other])
                    q += f" exclude stack_{other} {distract}"
                rows.append({"text": q, "stack": stack, "step": f"{stack}:{step}"})
    step_to_idx = {name: i for i, name in enumerate(sorted(set(step_names)))}
    return rows, step_to_idx


def build_vocab(rows: list[dict[str, str]], max_vocab: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for tok in tokenize(row["text"]):
            counts[tok] = counts.get(tok, 0) + 1
    pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:max_vocab]
    return {tok: i for i, (tok, _) in enumerate(pairs)}


def vectorize(rows: list[dict[str, str]], vocab: dict[str, int]) -> np.ndarray:
    x = np.zeros((len(rows), len(vocab)), dtype=np.float32)
    for i, row in enumerate(rows):
        for tok in tokenize(row["text"]):
            idx = vocab.get(tok)
            if idx is not None:
                x[i, idx] += 1.0
        norm = np.linalg.norm(x[i], ord=2)
        if norm > 0:
            x[i] /= norm
    return x


def labels(rows: list[dict[str, str]], step_to_idx: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    y_stack = np.zeros((len(rows),), dtype=np.int64)
    y_step = np.zeros((len(rows),), dtype=np.int64)
    for i, row in enumerate(rows):
        y_stack[i] = STACK_TO_IDX[row["stack"]]
        y_step[i] = step_to_idx[row["step"]]
    return y_stack, y_step


def softmax(z: np.ndarray) -> np.ndarray:
    z2 = z - z.max(axis=1, keepdims=True)
    e = np.exp(z2)
    return e / e.sum(axis=1, keepdims=True)


def acc(logits: np.ndarray, y: np.ndarray) -> float:
    return float((np.argmax(logits, axis=1) == y).mean())


def rule_step_predict(text: str, stack: str, step_to_idx: dict[str, int]) -> int:
    toks = set(tokenize(text))
    best_key = f"{stack}:{CHAIN_STEPS[stack][0]}"
    best_score = -1
    for step in CHAIN_STEPS[stack]:
        key = f"{stack}:{step}"
        kws = set(STEP_KEYWORDS[key])
        score = len(toks & kws)
        if score > best_score:
            best_score = score
            best_key = key
    return step_to_idx[best_key]


def split(rows: list[dict[str, str]], train_ratio: float, seed: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rng = np.random.default_rng(seed)
    idx = np.arange(len(rows))
    rng.shuffle(idx)
    cut = int(len(rows) * train_ratio)
    train = [rows[i] for i in idx[:cut]]
    test = [rows[i] for i in idx[cut:]]
    return train, test


def main() -> int:
    parser = argparse.ArgumentParser(description="Train voxel/vixel/vexel/boxels logic-chain classifiers")
    parser.add_argument("--samples-per-step", type=int, default=80)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--max-vocab", type=int, default=3000)
    parser.add_argument("--hidden-dim", type=int, default=48)
    parser.add_argument("--warmup-stack-epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=0.12)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=17)
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
    )
    args = parser.parse_args()

    rows, step_to_idx = synthesize_dataset(args.samples_per_step, args.seed)
    merkle_rows: list[dict[str, str]] = []
    if not args.disable_merkle_memory:
        merkle_rows = load_merkle_memory_rows(args.merkle_map, args.merkle_max_events)
        rows.extend(merkle_rows)
    train_rows, test_rows = split(rows, train_ratio=0.8, seed=args.seed)
    vocab = build_vocab(train_rows, args.max_vocab)
    x_train = vectorize(train_rows, vocab)
    x_test = vectorize(test_rows, vocab)
    y_stack_train, y_step_train = labels(train_rows, step_to_idx)
    y_stack_test, y_step_test = labels(test_rows, step_to_idx)

    rng = np.random.default_rng(args.seed)
    w_shared = rng.normal(scale=0.03, size=(len(vocab), args.hidden_dim)).astype(np.float32)
    b_shared = np.zeros((1, args.hidden_dim), dtype=np.float32)
    w_stack = rng.normal(scale=0.03, size=(args.hidden_dim, len(STACKS))).astype(np.float32)
    b_stack = np.zeros((1, len(STACKS)), dtype=np.float32)
    w_step = rng.normal(scale=0.03, size=(args.hidden_dim, len(step_to_idx))).astype(np.float32)
    b_step = np.zeros((1, len(step_to_idx)), dtype=np.float32)

    logs: list[dict[str, Any]] = []
    for epoch in range(1, args.epochs + 1):
        h = np.tanh(x_train @ w_shared + b_shared)

        # Stack head
        logits_stack = h @ w_stack + b_stack
        p_stack = softmax(logits_stack)
        oh_stack = np.eye(len(STACKS), dtype=np.float32)[y_stack_train]
        dlogits_stack = (p_stack - oh_stack) / len(x_train)
        dw_stack = h.T @ dlogits_stack + args.l2 * w_stack
        db_stack = dlogits_stack.sum(axis=0, keepdims=True)
        dh_stack = dlogits_stack @ w_stack.T

        # Step head (enabled after stack warmup)
        logits_step = h @ w_step + b_step
        if epoch > args.warmup_stack_epochs:
            p_step = softmax(logits_step)
            oh_step = np.eye(len(step_to_idx), dtype=np.float32)[y_step_train]
            dlogits_step = (p_step - oh_step) / len(x_train)
            dw_step = h.T @ dlogits_step + args.l2 * w_step
            db_step = dlogits_step.sum(axis=0, keepdims=True)
            dh_step = dlogits_step @ w_step.T
        else:
            dw_step = np.zeros_like(w_step)
            db_step = np.zeros_like(b_step)
            dh_step = np.zeros_like(h)

        dz = (dh_stack + dh_step) * (1 - h * h)
        dw_shared = x_train.T @ dz + args.l2 * w_shared
        db_shared = dz.sum(axis=0, keepdims=True)

        w_shared -= args.lr * dw_shared
        b_shared -= args.lr * db_shared
        w_stack -= args.lr * dw_stack
        b_stack -= args.lr * db_stack
        w_step -= args.lr * dw_step
        b_step -= args.lr * db_step

        if epoch == 1 or epoch % 5 == 0 or epoch == args.epochs:
            h_test = np.tanh(x_test @ w_shared + b_shared)
            log = {
                "epoch": epoch,
                "stack_train_acc": acc(logits_stack, y_stack_train),
                "stack_test_acc": acc(h_test @ w_stack + b_stack, y_stack_test),
                "step_train_acc": acc(logits_step, y_step_train),
                "step_test_acc": acc(h_test @ w_step + b_step, y_step_test),
            }
            logs.append(log)
            print(json.dumps(log))

    run_started = datetime.now(timezone.utc)
    run_id = run_started.strftime("%Y%m%dT%H%M%S") + f"{run_started.microsecond // 1000:03d}Z"
    run_dir = args.save_dir / f"voxel_stack_logic_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        run_dir / "model_weights.npz",
        w_shared=w_shared,
        b_shared=b_shared,
        w_stack=w_stack,
        b_stack=b_stack,
        w_step=w_step,
        b_step=b_step,
    )
    with (run_dir / "vocab.json").open("w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=True)
    with (run_dir / "chain_map.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "stacks": STACKS,
                "stack_roles": STACK_ROLES,
                "chain_steps": CHAIN_STEPS,
                "step_to_idx": step_to_idx,
            },
            f,
            indent=2,
            ensure_ascii=True,
        )

    h_test = np.tanh(x_test @ w_shared + b_shared)
    final = {
        "run_id": run_id,
        "rows_total": len(rows),
        "rows_train": len(train_rows),
        "rows_test": len(test_rows),
        "rows_merkle_replay": len(merkle_rows),
        "merkle_memory_enabled": not args.disable_merkle_memory,
        "merkle_map": str(args.merkle_map),
        "stack_roles": STACK_ROLES,
        "vocab_size": len(vocab),
        "stack_test_acc": acc(h_test @ w_stack + b_stack, y_stack_test),
        "step_test_acc": acc(h_test @ w_step + b_step, y_step_test),
        "artifacts_dir": str(run_dir),
    }
    pred_stack_idx = np.argmax(h_test @ w_stack + b_stack, axis=1)
    idx_to_stack = {v: k for k, v in STACK_TO_IDX.items()}
    hybrid_correct = 0
    oracle_stack_correct = 0
    for i, row in enumerate(test_rows):
        stack_name = idx_to_stack[int(pred_stack_idx[i])]
        pred_step = rule_step_predict(row["text"], stack_name, step_to_idx)
        if pred_step == y_step_test[i]:
            hybrid_correct += 1
        oracle_pred_step = rule_step_predict(row["text"], row["stack"], step_to_idx)
        if oracle_pred_step == y_step_test[i]:
            oracle_stack_correct += 1
    final["hybrid_step_test_acc"] = hybrid_correct / len(test_rows)
    final["rule_step_given_true_stack_acc"] = oracle_stack_correct / len(test_rows)
    with (run_dir / "report.json").open("w", encoding="utf-8") as f:
        json.dump({"config": vars(args), "epoch_logs": logs, "final_metrics": final}, f, indent=2, ensure_ascii=True, default=str)
    print(json.dumps(final, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
