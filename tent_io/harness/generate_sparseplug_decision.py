#!/usr/bin/env python3
"""Generate a deterministic SparsePlug device-profile decision record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sparseplug_sparsity import get_sparsity_target

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ram_bytes() -> int | None:
    try:
        if sys_platform() == "darwin":
            r = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if r.returncode == 0:
                return int(r.stdout.strip())
        if sys_platform() == "linux":
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        # KiB -> bytes
                        return int(line.split()[1]) * 1024
    except Exception:
        return None
    return None


def sys_platform() -> str:
    return platform.system().lower()


def profile_from_target(target: float) -> str:
    if target <= 0.55:
        return "dense"
    if target <= 0.80:
        return "balanced"
    return "sparse"


def sha256_obj(obj: dict[str, Any]) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SparsePlug decision JSON")
    parser.add_argument(
        "--device-id",
        default=os.environ.get("SPARSEPLUG_DEVICE_ID", platform.node() or "unknown-device"),
        help="Stable device identifier",
    )
    parser.add_argument(
        "--sparseplug-version",
        default=os.environ.get("SPARSEPLUG_VERSION", "local-dev"),
        help="SparsePlug runtime version string",
    )
    parser.add_argument(
        "--policy-context",
        default="{}",
        help="JSON object string for policy context",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "tent_io" / "harness" / "reports" / "sparseplug_decision.current.json",
        help="Output decision path",
    )
    args = parser.parse_args()

    try:
        policy_context = json.loads(args.policy_context)
        if not isinstance(policy_context, dict):
            raise ValueError("policy context must be JSON object")
    except Exception as exc:
        raise SystemExit(f"Invalid --policy-context JSON object: {exc}")

    target, source = get_sparsity_target()
    profile = profile_from_target(target)

    hardware_snapshot = {
        "cpu_cores": os.cpu_count() or 1,
        "ram_bytes": _ram_bytes() or 1,
        "accelerator": os.environ.get("SPARSEPLUG_ACCELERATOR", "unknown"),
        "platform": platform.platform(),
        "source": source,
        "target": round(target, 4),
    }

    deterministic_input = {
        "device_id": args.device_id,
        "sparseplug_version": args.sparseplug_version,
        "hardware_snapshot": hardware_snapshot,
        "policy_context": policy_context,
        "selected_profile": profile,
    }

    decision = {
        "decision_id": hashlib.sha256(
            f"{args.device_id}:{args.sparseplug_version}:{source}:{target}".encode("utf-8")
        ).hexdigest()[:16],
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "device_id": args.device_id,
        "sparseplug_version": args.sparseplug_version,
        "hardware_snapshot": hardware_snapshot,
        "policy_context": policy_context,
        "selected_profile": profile,
        "deterministic_inputs_hash": sha256_obj(deterministic_input),
    }
    decision["decision_hash"] = sha256_obj(decision)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(decision, f, indent=2, ensure_ascii=True)

    print(json.dumps({"out": str(args.out), "selected_profile": profile, "source": source}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
