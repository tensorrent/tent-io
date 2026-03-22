#!/usr/bin/env python3
"""Deterministically evaluate best voxel stack logic checkpoint."""

from __future__ import annotations

import argparse
import json
import re
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
LEGACY_STACK_ROLES: dict[str, str] = {
    "voxel": "volume grid structure",
    "vixel": "intent/semantic routing field",
    "vexel": "execution vector/stateflow representation",
    "boxels": "partition/consensus mesh envelopes",
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
LEGACY_STACK_CUES: dict[str, list[str]] = {
    "voxel": ["volume", "gridcell", "occupancy", "octree", "spatial"],
    "vixel": ["intent", "field", "semantic", "reasoning", "confidence"],
    "vexel": ["vector", "edge", "execution", "transition", "stateflow"],
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


def vectorize(rows: list[dict[str, str]], vocab: dict[str, int]) -> np.ndarray:
    x = np.zeros((len(rows), len(vocab)), dtype=np.float32)
    for i, row in enumerate(rows):
        for tok in tokenize(row["text"]):
            idx = vocab.get(tok)
            if idx is not None:
                x[i, idx] += 1.0
        n = np.linalg.norm(x[i], ord=2)
        if n > 0:
            x[i] /= n
    return x


def labels(rows: list[dict[str, str]], step_to_idx: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    ys = np.zeros((len(rows),), dtype=np.int64)
    yp = np.zeros((len(rows),), dtype=np.int64)
    for i, row in enumerate(rows):
        ys[i] = STACK_TO_IDX[row["stack"]]
        yp[i] = step_to_idx[row["step"]]
    return ys, yp


def rule_step_predict(text: str, stack: str, step_to_idx: dict[str, int]) -> int:
    toks = set(tokenize(text))
    best_key = f"{stack}:{CHAIN_STEPS[stack][0]}"
    best_score = -1
    for step in CHAIN_STEPS[stack]:
        key = f"{stack}:{step}"
        score = len(toks & set(STEP_KEYWORDS[key]))
        if score > best_score:
            best_score = score
            best_key = key
    return step_to_idx[best_key]


def acc(pred: np.ndarray, y: np.ndarray) -> float:
    return float((pred == y).mean())


def synth_eval_set(
    step_to_idx: dict[str, int],
    samples_per_step: int,
    seed: int,
    stack_cues: dict[str, list[str]],
    stack_roles: dict[str, str],
) -> list[dict[str, str]]:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, str]] = []
    for stack, steps in CHAIN_STEPS.items():
        for step in steps:
            key = f"{stack}:{step}"
            for _ in range(samples_per_step):
                verb = rng.choice(["run", "apply", "execute", "compute", "trigger"])
                mod = rng.choice(["now", "for node", "for profile", "under sparse mode", "under dense mode"])
                kw = rng.choice(STEP_KEYWORDS[key], size=2, replace=False)
                stack_kw = rng.choice(stack_cues[stack], size=2, replace=False)
                q = (
                    f"{verb} stack_{stack} {stack} chain with {stack_kw[0]} {stack_kw[1]} "
                    f"and {kw[0]} {kw[1]} role_{stack}_{stack_roles[stack].replace(' ', '_')} {mod}"
                )
                if rng.random() < 0.35:
                    other = rng.choice([s for s in STACKS if s != stack])
                    distract = rng.choice(stack_cues[other])
                    q += f" exclude stack_{other} {distract}"
                rows.append({"text": q, "stack": stack, "step": key})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate best voxel stack checkpoint")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/training"),
    )
    parser.add_argument(
        "--best-link",
        choices=["best_voxel_stack", "best_voxel_hybrid_step", "best_voxel_rule_step"],
        default="best_voxel_hybrid_step",
    )
    parser.add_argument("--samples-per-step", type=int, default=40)
    parser.add_argument("--seed", type=int, default=19)
    args = parser.parse_args()

    run_dir = (args.reports_dir / args.best_link).resolve()
    if not run_dir.exists():
        raise SystemExit(f"Best link not found: {args.reports_dir / args.best_link}")

    with (run_dir / "vocab.json").open("r", encoding="utf-8") as f:
        vocab = json.load(f)
    with (run_dir / "chain_map.json").open("r", encoding="utf-8") as f:
        chain_map = json.load(f)
    step_to_idx = {k: int(v) for k, v in chain_map["step_to_idx"].items()}

    weights = np.load(run_dir / "model_weights.npz")
    w_shared = weights["w_shared"]
    b_shared = weights["b_shared"]
    w_stack = weights["w_stack"]
    b_stack = weights["b_stack"]
    w_step = weights["w_step"]
    b_step = weights["b_step"]

    roles_from_checkpoint = chain_map.get("stack_roles")
    if isinstance(roles_from_checkpoint, dict) and roles_from_checkpoint.get("vexel") == STACK_ROLES["vexel"]:
        active_roles = STACK_ROLES
        active_cues = STACK_CUES
        taxonomy_profile = "voxel_family_public_vexel"
    else:
        active_roles = LEGACY_STACK_ROLES
        active_cues = LEGACY_STACK_CUES
        taxonomy_profile = "legacy"

    rows = synth_eval_set(
        step_to_idx,
        samples_per_step=args.samples_per_step,
        seed=args.seed,
        stack_cues=active_cues,
        stack_roles=active_roles,
    )
    x = vectorize(rows, vocab)
    y_stack, y_step = labels(rows, step_to_idx)

    h = np.tanh(x @ w_shared + b_shared)
    p_stack = np.argmax(h @ w_stack + b_stack, axis=1)
    p_step = np.argmax(h @ w_step + b_step, axis=1)

    idx_to_stack = {v: k for k, v in STACK_TO_IDX.items()}
    hybrid = []
    oracle = []
    for i, row in enumerate(rows):
        stack_name = idx_to_stack[int(p_stack[i])]
        hybrid.append(rule_step_predict(row["text"], stack_name, step_to_idx))
        oracle.append(rule_step_predict(row["text"], row["stack"], step_to_idx))

    out = {
        "checkpoint": str(run_dir),
        "best_link": args.best_link,
        "stack_roles": active_roles,
        "taxonomy_profile": taxonomy_profile,
        "samples_per_step": args.samples_per_step,
        "seed": args.seed,
        "rows_eval": len(rows),
        "stack_acc": acc(p_stack, y_stack),
        "step_head_acc": acc(p_step, y_step),
        "hybrid_step_acc": acc(np.array(hybrid), y_step),
        "rule_step_given_true_stack_acc": acc(np.array(oracle), y_step),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
