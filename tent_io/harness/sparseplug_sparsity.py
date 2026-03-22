#!/usr/bin/env python3
"""
SparsePlug sparsity for tent_io/ODIN.
Uses SPARSEPLUG_TARGET from env if set; else derives from system RAM
to match archive/ignite.sh logic (GHOST 0.90, STANDARD 0.70, FULL 0.50).
No external calls.
"""

import os
import sys
from pathlib import Path

# Defaults from SparsePlug/ignite.sh: <16GB -> 0.90, 16-32GB -> 0.70, >32GB -> 0.50
RAM_GB_THRESHOLD_LOW = 16
RAM_GB_THRESHOLD_HIGH = 32
SPARSITY_GHOST = 0.90   # Mobile / <16GB
SPARSITY_STANDARD = 0.70  # Desktop / 16-32GB
SPARSITY_FULL = 0.50    # Server / >32GB


def _ram_gb() -> float | None:
    try:
        if sys.platform == "darwin":
            import subprocess
            r = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if r.returncode == 0:
                return int(r.stdout.strip()) / (1024**3)
        elif sys.platform == "linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) / (1024 * 1024)
    except Exception:
        pass
    return None


def get_sparsity_target() -> tuple[float, str]:
    """
    Returns (sparsity_target, source).
    sparsity_target: float in [0, 1] (fraction sparse / pruned).
    source: "env", "ram_ghost", "ram_standard", "ram_full", or "default".
    """
    env_val = os.environ.get("SPARSEPLUG_TARGET")
    if env_val is not None:
        try:
            v = float(env_val)
            if 0 <= v <= 1:
                return (v, "env")
        except ValueError:
            pass
    ram = _ram_gb()
    if ram is not None:
        if ram < RAM_GB_THRESHOLD_LOW:
            return (SPARSITY_GHOST, "ram_ghost")
        if ram < RAM_GB_THRESHOLD_HIGH:
            return (SPARSITY_STANDARD, "ram_standard")
        return (SPARSITY_FULL, "ram_full")
    return (SPARSITY_STANDARD, "default")


def main() -> int:
    target, source = get_sparsity_target()
    print(f"{target:.2f}")
    print(f"# source={source}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
