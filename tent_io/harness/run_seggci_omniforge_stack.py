#!/usr/bin/env python3
"""Deterministic orchestrator: SparsePlug -> SEGGCI -> OmniForge (+optional Bingo).

This binds the current SparsePlug decision gate to SEGGCI runtime and OmniForge
seed generation with an auditable run manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rys_circuit_adapter import run_rys

PROFILE_TO_TARGET = {
    "dense": 0.50,
    "balanced": 0.70,
    "sparse": 0.90,
}


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_obj(obj: dict[str, Any]) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256_text(payload)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_sparseplug_decision(decision: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    required = [
        "decision_id",
        "timestamp_utc",
        "device_id",
        "sparseplug_version",
        "selected_profile",
        "deterministic_inputs_hash",
        "decision_hash",
    ]
    for key in required:
        if key not in decision:
            errors.append(f"missing field: {key}")
    profile = decision.get("selected_profile")
    if profile not in PROFILE_TO_TARGET:
        errors.append("invalid selected_profile")

    deterministic_input = {
        "device_id": decision.get("device_id"),
        "sparseplug_version": decision.get("sparseplug_version"),
        "hardware_snapshot": decision.get("hardware_snapshot", {}),
        "policy_context": decision.get("policy_context", {}),
        "selected_profile": profile,
    }
    if decision.get("deterministic_inputs_hash") != sha256_obj(deterministic_input):
        errors.append("deterministic_inputs_hash mismatch")

    tmp = dict(decision)
    received = tmp.pop("decision_hash", None)
    if received != sha256_obj(tmp):
        errors.append("decision_hash mismatch")
    return (len(errors) == 0, errors)


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


def apply_env(env_map: dict[str, str]) -> None:
    for k, v in env_map.items():
        os.environ[k] = v


def run_seggci(query: str) -> dict[str, Any]:
    ws = Path("/Users/coo-koba42/dev/seggci_workspace")
    if not ws.exists():
        return {"status": "missing_workspace", "path": str(ws)}

    if str(ws) not in sys.path:
        sys.path.insert(0, str(ws))
    try:
        from sovereign_vixel.integrator import SovereignInstance  # type: ignore
    except Exception as exc:
        return {"status": "import_error", "error": str(exc)}

    try:
        inst = SovereignInstance(instance_id="seggci-omniforge-bridge")
        status = inst.status()
        reason = inst.reason(query)
        return {"status": "ok", "instance_status": status, "reason_result": reason}
    except Exception as exc:
        return {"status": "runtime_error", "error": str(exc)}


def run_omniforge_compile(payload: dict[str, Any]) -> dict[str, Any]:
    compiler_path = Path("/Users/coo-koba42/dev/omni_forge_compiler.py")
    if not compiler_path.exists():
        return {"status": "missing_compiler", "path": str(compiler_path)}

    spec = importlib.util.spec_from_file_location("omni_forge_compiler", compiler_path)
    if not spec or not spec.loader:
        return {"status": "load_error", "error": "spec loader unavailable"}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    if not hasattr(mod, "OmniForgeCompiler"):
        return {"status": "missing_class", "error": "OmniForgeCompiler not found"}
    try:
        compiler = mod.OmniForgeCompiler()
        seed = compiler.compress_to_seed(payload)
        reconstructed = compiler.decompress_seed(seed)
        return {
            "status": "ok",
            "seed": seed,
            "seed_len_bytes": len(seed.encode("utf-8")),
            "reconstructed": reconstructed,
        }
    except Exception as exc:
        return {"status": "runtime_error", "error": str(exc)}


def run_bingo_stage(
    env_map: dict[str, str],
    instruction: str,
    context_id: str,
    user_id: str,
    system_seed: int,
    bingo_core_path: str,
) -> dict[str, Any]:
    for k, v in env_map.items():
        os.environ[k] = v

    root = Path("/Users/coo-koba42/dev")
    candidate_paths = [
        root / "prime-sparse-saas" / "bingo-os-core",
        root / "archive" / "cleanup_2026_01_30" / "prime-sparse-saas" / "bingo-os-core",
    ]
    if bingo_core_path:
        candidate_paths.insert(0, Path(bingo_core_path))

    for p in candidate_paths:
        if p.exists() and str(p) not in sys.path:
            sys.path.append(str(p))

    try:
        bingo_mod = importlib.import_module("bingo_os")
    except Exception as exc:
        return {
            "status": "bingo_os_unavailable",
            "error": str(exc),
            "hint": "Provide --bingo-core-path or install bingo_os module.",
        }
    if not hasattr(bingo_mod, "BingoOS"):
        return {"status": "bingo_os_missing_class", "error": "BingoOS class not found"}

    try:
        bingo = bingo_mod.BingoOS(user_id=user_id, system_seed=system_seed)
        result = bingo.process_thought(instruction, context_id=context_id)
        return {
            "status": "ok",
            "instruction": instruction,
            "context_id": context_id,
            "result": result,
        }
    except Exception as exc:
        return {"status": "runtime_error", "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SparsePlug->SEGGCI->OmniForge deterministic stack")
    parser.add_argument(
        "--decision-json",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/sparseplug_decision.current.json"),
    )
    parser.add_argument("--query", default="system profile check")
    parser.add_argument("--strict", action="store_true", help="Fail closed on stage errors")
    parser.add_argument("--with-bingo", action="store_true", help="Include Bingo OS stage")
    parser.add_argument("--with-rys", action="store_true", default=True, help="Include RYS stage")
    parser.add_argument("--no-rys", action="store_true", help="Disable RYS stage")
    parser.add_argument("--rys-stability-threshold", type=float, default=0.55)
    parser.add_argument("--rys-max-iters", type=int, default=12)
    parser.add_argument("--bingo-core-path", default="", help="Path to bingo-os-core for Bingo stage")
    parser.add_argument("--bingo-instruction", default="System Check")
    parser.add_argument("--bingo-context-id", default="SEGGCI_EXEC")
    parser.add_argument("--bingo-user-id", default="coo-koba42")
    parser.add_argument("--bingo-system-seed", type=lambda x: int(x, 0), default=int("0xCAFEBABE", 16))
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/seggci_omniforge_run.current.json"),
    )
    args = parser.parse_args()

    run = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "strict": args.strict,
        "stages": {},
    }

    # Stage 1: SparsePlug decision load + validation
    if not args.decision_json.exists():
        run["stages"]["sparseplug"] = {"status": "missing_decision", "path": str(args.decision_json)}
        rc = 2
    else:
        decision = load_json(args.decision_json)
        valid, errors = validate_sparseplug_decision(decision)
        env_map = derive_env(decision) if valid else {}
        run["stages"]["sparseplug"] = {
            "status": "ok" if valid else "invalid",
            "errors": errors,
            "decision_path": str(args.decision_json),
            "env": env_map,
            "selected_profile": decision.get("selected_profile"),
            "decision_hash": decision.get("decision_hash"),
        }
        if valid:
            apply_env(env_map)
        rc = 0 if valid else 2

    # Stage 2: SEGGCI runtime
    if rc == 0:
        if args.with_bingo:
            bingo = run_bingo_stage(
                run["stages"]["sparseplug"]["env"],
                instruction=args.bingo_instruction,
                context_id=args.bingo_context_id,
                user_id=args.bingo_user_id,
                system_seed=args.bingo_system_seed,
                bingo_core_path=args.bingo_core_path,
            )
            run["stages"]["bingo"] = bingo
            if args.strict and bingo.get("status") != "ok":
                rc = 2

    if rc == 0:
        seggci = run_seggci(args.query)
        run["stages"]["seggci"] = seggci
        if seggci.get("status") != "ok":
            rc = 2

    # Stage 3: RYS convergence stage
    if rc == 0:
        if args.with_rys and not args.no_rys:
            rys = run_rys(
                query=args.query,
                seggci_reason_result=run["stages"]["seggci"].get("reason_result", {}),
                max_iters=args.rys_max_iters,
                stability_threshold=args.rys_stability_threshold,
            )
            run["stages"]["rys"] = rys
            # In provisional mode, allow strict pass when stability threshold passes
            # even if max_iters is hit before epsilon convergence.
            if args.strict and not (rys.get("converged") or rys.get("passes_threshold")):
                rc = 2

    # Stage 4: OmniForge compile from deterministic payload
    if rc == 0:
        compile_payload = {
            "query": args.query,
            "sparseplug": run["stages"]["sparseplug"],
            "seggci_status": run["stages"]["seggci"].get("instance_status", {}),
            "seggci_reason_keys": sorted(run["stages"]["seggci"].get("reason_result", {}).keys()),
            "rys": run["stages"].get("rys", {}),
        }
        omni = run_omniforge_compile(compile_payload)
        run["stages"]["omniforge"] = omni
        if omni.get("status") != "ok":
            rc = 2

    # Final audit fields
    run["status"] = "ok" if rc == 0 else "partial_or_failed"
    run["run_hash"] = sha256_obj(run)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(run, f, indent=2, ensure_ascii=True)

    print(json.dumps({"out": str(args.out), "status": run["status"], "run_hash": run["run_hash"]}, indent=2))
    if args.strict and rc != 0:
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
