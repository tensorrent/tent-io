#!/usr/bin/env python3
"""Bridge SparsePlug profile decisions into Bingo OS execution context.

This script supports two modes:
1) `env` mode (default): derive deterministic runtime env from SparsePlug decision.
2) `exec` mode: attempt to run a thought through BingoOS if module is available.

The bridge is fail-closed in strict mode.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


PROFILE_TO_TARGET = {
    "dense": 0.50,
    "balanced": 0.70,
    "sparse": 0.90,
}


def load_decision(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def derive_env(decision: dict[str, Any]) -> dict[str, str]:
    profile = decision["selected_profile"]
    target = PROFILE_TO_TARGET[profile]
    return {
        "SPARSEPLUG_PROFILE": profile,
        "SPARSEPLUG_TARGET": f"{target:.2f}",
        "SPARSEPLUG_DECISION_ID": str(decision.get("decision_id", "")),
        "SPARSEPLUG_DECISION_HASH": str(decision.get("decision_hash", "")),
        "SPARSEPLUG_SOURCE": str(decision.get("hardware_snapshot", {}).get("source", "")),
    }


def set_env(env_map: dict[str, str]) -> None:
    for k, v in env_map.items():
        os.environ[k] = v


def try_import_bingo_os(extra_paths: list[Path]) -> Any:
    for p in extra_paths:
        if p.exists() and str(p) not in sys.path:
            sys.path.append(str(p))
    return importlib.import_module("bingo_os")


def run_bingo_exec(args: argparse.Namespace, env_map: dict[str, str]) -> int:
    set_env(env_map)

    # Known historical locations first, then optional explicit path.
    root = Path("/Users/coo-koba42/dev")
    candidate_paths = [
        root / "prime-sparse-saas" / "bingo-os-core",
        root / "archive" / "cleanup_2026_01_30" / "prime-sparse-saas" / "bingo-os-core",
    ]
    if args.bingo_core_path:
        candidate_paths.insert(0, Path(args.bingo_core_path))

    try:
        bingo_mod = try_import_bingo_os(candidate_paths)
    except Exception as exc:
        payload = {
            "status": "bingo_os_unavailable",
            "error": str(exc),
            "hint": "Provide --bingo-core-path or install bingo_os module. Use --mode env to continue without exec.",
            "env": env_map,
        }
        print(json.dumps(payload, indent=2))
        return 2 if args.strict else 0

    if not hasattr(bingo_mod, "BingoOS"):
        payload = {
            "status": "bingo_os_missing_class",
            "error": "Module imported but BingoOS class not found.",
            "env": env_map,
        }
        print(json.dumps(payload, indent=2))
        return 2 if args.strict else 0

    bingo = bingo_mod.BingoOS(user_id=args.user_id, system_seed=args.system_seed)
    result = bingo.process_thought(args.instruction, context_id=args.context_id)
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": "exec",
                "instruction": args.instruction,
                "context_id": args.context_id,
                "env": env_map,
                "result": result,
            },
            indent=2,
            default=str,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge SparsePlug decision to Bingo OS runtime")
    parser.add_argument(
        "--decision-json",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/sparseplug_decision.current.json"),
    )
    parser.add_argument("--mode", choices=["env", "exec"], default="env")
    parser.add_argument("--strict", action="store_true", help="Fail closed if BingoOS execution is unavailable")

    # Exec-mode options
    parser.add_argument("--bingo-core-path", default="", help="Path to bingo-os-core folder")
    parser.add_argument("--instruction", default="System Check")
    parser.add_argument("--context-id", default="SEGGCI_EXEC")
    parser.add_argument("--user-id", default="coo-koba42")
    parser.add_argument("--system-seed", type=lambda x: int(x, 0), default=int("0xCAFEBABE", 16))
    args = parser.parse_args()

    if not args.decision_json.exists():
        raise SystemExit(f"Decision file not found: {args.decision_json}")

    decision = load_decision(args.decision_json)
    profile = decision.get("selected_profile")
    if profile not in PROFILE_TO_TARGET:
        raise SystemExit(f"Invalid selected_profile in decision: {profile}")

    env_map = derive_env(decision)
    if args.mode == "env":
        print(json.dumps({"status": "ok", "mode": "env", "env": env_map}, indent=2))
        return 0

    return run_bingo_exec(args, env_map)


if __name__ == "__main__":
    raise SystemExit(main())
