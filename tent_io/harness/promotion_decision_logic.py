"""
Shared promotion decision helpers (alignment streak, external margin, contested tie-break).

Used by ``compute_promotion_decision.py`` and tests. Scope: as documented in
``docs/PROMOTION_POLICY_GOVERNANCE.md``.
"""

from __future__ import annotations

import json
from typing import Any

VALID_EXPAND_SLOTS = frozenset({"expand_s1", "expand_s2"})

METRIC_KEYS = ("mmlu_pro_acc", "gpqa_acc", "long_context_acc", "consistency_score")


def mean_metric_score(block: dict[str, Any] | None) -> float | None:
    if not isinstance(block, dict):
        return None
    m = block.get("metrics")
    if not isinstance(m, dict):
        return None
    vals: list[float] = []
    for k in METRIC_KEYS:
        v = m.get(k)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    if not vals:
        return None
    return sum(vals) / len(vals)


def external_aggregate_margin(ext_data: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    """
    Returns (s1_mean, s2_mean, s1_minus_s2_signed).
    Used for tie-break magnitude and direction checks.
    """
    s1 = ext_data.get("expand_s1") if isinstance(ext_data.get("expand_s1"), dict) else {}
    s2 = ext_data.get("expand_s2") if isinstance(ext_data.get("expand_s2"), dict) else {}
    a1 = mean_metric_score(s1)
    a2 = mean_metric_score(s2)
    if a1 is None or a2 is None:
        return (a1, a2, None)
    return (a1, a2, a1 - a2)


def alignment_streak_after_run(history_lines: list[str], aligned: bool) -> int:
    """
    Consecutive **aligned** runs only. Resets to 0 when ``aligned`` is false.
    After a contested or insufficient run, the next aligned run starts at 1.
    """
    if not aligned:
        return 0
    if not history_lines:
        return 1
    try:
        last = json.loads(history_lines[-1].strip())
    except (json.JSONDecodeError, ValueError, TypeError):
        return 1
    if last.get("aligned") is True:
        return int(last.get("aligned_streak", 0)) + 1
    return 1


def tie_break_momentum(contested: bool, margin_abs: float | None, margin_floor: float) -> bool:
    """Momentum uses a minimum margin floor (typically 0.01) for streak continuity."""
    return bool(contested and margin_abs is not None and margin_abs >= margin_floor)


def per_metric_deltas(ext_data: dict[str, Any]) -> dict[str, float | None]:
    """Per-metric s1−s2 deltas; prefer ``deltas_s1_minus_s2`` from compare JSON."""
    pre = ext_data.get("deltas_s1_minus_s2")
    if isinstance(pre, dict):
        out: dict[str, float | None] = {}
        for k in METRIC_KEYS:
            v = pre.get(k)
            if v is None:
                out[k] = None
            elif isinstance(v, (int, float)):
                out[k] = float(v)
            else:
                out[k] = None
        return out
    s1 = ext_data.get("expand_s1") if isinstance(ext_data.get("expand_s1"), dict) else {}
    s2 = ext_data.get("expand_s2") if isinstance(ext_data.get("expand_s2"), dict) else {}
    m1 = s1.get("metrics") if isinstance(s1.get("metrics"), dict) else {}
    m2 = s2.get("metrics") if isinstance(s2.get("metrics"), dict) else {}
    out2: dict[str, float | None] = {}
    for k in METRIC_KEYS:
        a = m1.get(k)
        b = m2.get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            out2[k] = float(a) - float(b)
        else:
            out2[k] = None
    return out2


def agreement_ratio_for_favor(ext_data: dict[str, Any], favored: str) -> float | None:
    """
    Fraction of **nonzero** per-metric deltas that point in the direction of ``favored``
    (expand_s1 ⇒ delta > 0, expand_s2 ⇒ delta < 0). None if no usable deltas.
    """
    if favored not in VALID_EXPAND_SLOTS:
        return None
    deltas = per_metric_deltas(ext_data)
    nonzero: list[float] = []
    for k in METRIC_KEYS:
        d = deltas.get(k)
        if d is None:
            continue
        if abs(d) <= 1e-12:
            continue
        nonzero.append(d)
    if not nonzero:
        return None
    if favored == "expand_s1":
        matches = sum(1 for d in nonzero if d > 0)
    else:
        matches = sum(1 for d in nonzero if d < 0)
    return matches / len(nonzero)


def tie_break_confidence(
    *,
    margin_abs: float,
    tb_streak: int,
    streak_required: int,
    agreement_ratio: float,
    best_profile: dict[str, Any],
    relax_drift: bool,
    target_margin: float = 0.03,
    drift_tol: float = 1e-6,
) -> tuple[float, dict[str, float]]:
    """
    Weighted confidence in [0, 1]: margin strength, streak, agreement, drift stability.
    """
    M = min(margin_abs / target_margin, 1.0) if target_margin > 0 else 0.0
    sr = float(streak_required) if streak_required > 0 else 1.0
    S = min(float(tb_streak) / sr, 1.0)
    A = max(0.0, min(1.0, agreement_ratio))
    D = drift_stability_component(best_profile, relax_drift=relax_drift, drift_tol=drift_tol)
    conf = 0.35 * M + 0.25 * S + 0.25 * A + 0.15 * D
    components = {"M": M, "S": S, "A": A, "D": D}
    return conf, components


def linear_percentile(values: list[float], p: float) -> float:
    """
    Linear interpolation percentile, ``p`` in [0, 100].
    Matches common ``numpy.percentile(..., interpolation='linear')`` behavior for interior points.
    """
    if not values:
        raise ValueError("linear_percentile: empty values")
    xs = sorted(values)
    n = len(xs)
    if n == 1:
        return xs[0]
    k = (n - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, n - 1)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (k - lo) * (xs[hi] - xs[lo])


def confidence_percentile_rank(value: float, historical: list[float]) -> float | None:
    """Fraction of historical samples strictly less than ``value`` (0–1). None if no history."""
    if not historical:
        return None
    below = sum(1 for s in historical if s < value)
    return below / len(historical)


def contested_tie_break_confidences_from_history_lines(
    lines: list[str],
    *,
    max_tail: int,
) -> list[float]:
    """
    From NDJSON lines (oldest first), collect ``tie_break_confidence`` for rows with
    ``decision_state == \"contested\"``, then keep the last ``max_tail`` values.
    """
    out: list[float] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("decision_state") != "contested":
            continue
        tc = row.get("tie_break_confidence")
        if isinstance(tc, (int, float)):
            out.append(float(tc))
    if max_tail > 0 and len(out) > max_tail:
        out = out[-max_tail:]
    return out


def adaptive_effective_threshold(
    static_threshold: float,
    *,
    historical_confidences: list[float],
    percentile: float = 75.0,
    clamp_min: float = 0.65,
    clamp_max: float = 0.85,
    min_samples: int = 3,
) -> tuple[float, float | None]:
    """
    Returns ``(effective_threshold, adaptive_raw_or_none)``.
    ``effective = max(static, clamped_percentile)`` when enough samples; else ``static`` and None.
    """
    if len(historical_confidences) < min_samples:
        return static_threshold, None
    raw = linear_percentile(historical_confidences, percentile)
    adaptive = max(clamp_min, min(clamp_max, raw))
    return max(static_threshold, adaptive), adaptive


def drift_stability_component(
    best_profile: dict[str, Any],
    *,
    relax_drift: bool,
    drift_tol: float = 1e-6,
) -> float:
    """Drift stability in [0, 1] for confidence; 1.0 when drift≈0 or check relaxed."""
    if relax_drift:
        return 1.0
    raw = best_profile.get("train_eval_drift")
    if raw is None:
        return 1.0
    try:
        v = abs(float(raw))
    except (TypeError, ValueError):
        return 0.0
    if v <= 1e-12:
        return 1.0
    return max(0.0, 1.0 - v / drift_tol) if drift_tol > 0 else 0.0


def external_tie_break_streak(
    history_lines: list[str],
    *,
    contested: bool,
    enabled: bool,
    margin_abs: float | None,
    margin_floor: float,
    ext_favored_slot: str | None,
) -> int:
    """
    Consecutive runs where contested tie-break *momentum* holds (margin strong enough,
    same external favored slot). Resets when margin too weak or not contested.
    """
    if not enabled:
        return 0
    if not tie_break_momentum(contested, margin_abs, margin_floor):
        return 0
    if ext_favored_slot not in VALID_EXPAND_SLOTS:
        return 0
    if not history_lines:
        return 1
    try:
        last = json.loads(history_lines[-1].strip())
    except (json.JSONDecodeError, ValueError, TypeError):
        return 1
    last_fav = last.get("external_favored_slot")
    last_tb = last.get("external_tie_break_streak")
    last_margin = last.get("external_margin_abs")
    last_ok = (
        last.get("tie_break_momentum") is True
        and last_fav == ext_favored_slot
        and isinstance(last_margin, (int, float))
        and float(last_margin) >= margin_floor
    )
    if last_ok and isinstance(last_tb, int):
        return last_tb + 1
    return 1


def drift_near_zero(best_profile: dict[str, Any], *, eps: float = 1e-9) -> bool:
    raw = best_profile.get("train_eval_drift")
    if raw is None:
        return True
    try:
        return abs(float(raw)) < eps
    except (TypeError, ValueError):
        return False
