#!/usr/bin/env python3
"""Validate a SparsePlug decision record against schema + deterministic hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


HEX64 = re.compile(r"^[a-fA-F0-9]{64}$")
PROFILE_SET = {"dense", "balanced", "sparse"}


def sha256_obj(obj: dict[str, Any]) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_minimal_schema(decision: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "decision_id",
        "timestamp_utc",
        "device_id",
        "sparseplug_version",
        "selected_profile",
        "deterministic_inputs_hash",
    ]
    for key in required:
        if key not in decision:
            errors.append(f"missing required field: {key}")

    if "selected_profile" in decision and decision["selected_profile"] not in PROFILE_SET:
        errors.append("selected_profile must be dense|balanced|sparse")

    for hash_key in ("deterministic_inputs_hash", "decision_hash"):
        if hash_key in decision and not isinstance(decision[hash_key], str):
            errors.append(f"{hash_key} must be string")
        if hash_key in decision and isinstance(decision[hash_key], str) and not HEX64.match(decision[hash_key]):
            errors.append(f"{hash_key} must be 64-char hex")

    return errors


def validate_hashes(decision: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    deterministic_input = {
        "device_id": decision.get("device_id"),
        "sparseplug_version": decision.get("sparseplug_version"),
        "hardware_snapshot": decision.get("hardware_snapshot", {}),
        "policy_context": decision.get("policy_context", {}),
        "selected_profile": decision.get("selected_profile"),
    }
    expected_inputs_hash = sha256_obj(deterministic_input)
    if decision.get("deterministic_inputs_hash") != expected_inputs_hash:
        errors.append("deterministic_inputs_hash mismatch")

    if "decision_hash" in decision:
        received = decision["decision_hash"]
        tmp = dict(decision)
        # Recompute over payload without decision_hash.
        tmp.pop("decision_hash", None)
        expected_decision_hash = sha256_obj(tmp)
        if received != expected_decision_hash:
            errors.append("decision_hash mismatch")

    return errors


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SparsePlug decision record")
    parser.add_argument(
        "--decision-json",
        type=Path,
        required=True,
        help="Path to sparseplug decision JSON",
    )
    parser.add_argument(
        "--schema-json",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/specs/sparseplug_device_profile.schema.json"),
        help="Schema path (optional metadata check).",
    )
    parser.add_argument(
        "--strict-hash",
        action="store_true",
        help="Fail if deterministic_inputs_hash/decision_hash checks fail.",
    )
    args = parser.parse_args()

    if not args.decision_json.exists():
        raise SystemExit(f"Decision file not found: {args.decision_json}")

    decision = load_json(args.decision_json)
    errors = validate_minimal_schema(decision)

    # Optional: if jsonschema is installed, enforce full schema too.
    if args.schema_json.exists():
        try:
            import jsonschema  # type: ignore

            schema = load_json(args.schema_json)
            jsonschema.validate(decision, schema)  # type: ignore[arg-type]
        except ModuleNotFoundError:
            # Fallback to minimal schema checks only.
            pass
        except Exception as exc:  # pragma: no cover
            errors.append(f"jsonschema validation error: {exc}")

    hash_errors = validate_hashes(decision)
    if args.strict_hash:
        errors.extend(hash_errors)

    result = {
        "decision_json": str(args.decision_json),
        "valid": len(errors) == 0,
        "errors": errors,
        "hash_checks": {
            "strict": args.strict_hash,
            "errors": hash_errors,
        },
    }
    print(json.dumps(result, indent=2))
    return 0 if len(errors) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
