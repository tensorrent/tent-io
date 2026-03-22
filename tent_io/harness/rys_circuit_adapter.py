#!/usr/bin/env python3
"""Deterministic RYS adapter with pluggable future implementation.

This adapter is intentionally minimal and stable so the pipeline can run while
the full RYS circuit is still under construction.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _hash_to_unit_interval(text: str) -> float:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # Use 52 bits to keep deterministic float conversion stable.
    x = int(h[:13], 16)  # 13 hex chars ~= 52 bits
    return x / float((1 << 52) - 1)


def _state_hash(value: float, target: float, depth: int) -> str:
    payload = f"{value:.15f}|{target:.15f}|{depth}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_rys(
    query: str,
    seggci_reason_result: dict[str, Any],
    max_iters: int = 12,
    convergence_eps: float = 1e-5,
    stability_threshold: float = 0.55,
) -> dict[str, Any]:
    """Run deterministic fixed-point refinement and emit RYS metrics.

    The model is a bounded iterative map:
      x_{t+1} = 0.62*x_t + 0.38*target
    which converges monotonically toward `target`.
    """

    reason_keys = sorted(seggci_reason_result.keys())
    seed_material = json.dumps(
        {"query": query, "reason_keys": reason_keys},
        sort_keys=True,
        ensure_ascii=True,
    )
    target = _hash_to_unit_interval(seed_material + "::target")
    value = _hash_to_unit_interval(seed_material + "::init")

    converged = False
    depth = 0
    last_delta = None
    for depth in range(1, max_iters + 1):
        nxt = (0.62 * value) + (0.38 * target)
        delta = abs(nxt - value)
        value = nxt
        last_delta = delta
        if delta <= convergence_eps:
            converged = True
            break

    # Stability: 1.0 means perfectly aligned to target fixed point.
    stability = max(0.0, min(1.0, 1.0 - abs(value - target)))
    fixed_hash = _state_hash(value, target, depth)

    return {
        "status": "ok",
        "mode": "deterministic_fallback",
        "converged": converged,
        "depth": depth,
        "stability": stability,
        "stability_threshold": stability_threshold,
        "passes_threshold": stability >= stability_threshold,
        "last_delta": last_delta,
        "fixed_point_hash": fixed_hash,
    }
