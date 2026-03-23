"""
Contested tie-break trajectory helpers: distance, crossings, dynamics, stability heuristics.

Used by ``visualize_decision_surface.py`` and optionally ``compute_promotion_decision.py``.
Scope: as documented in ``docs/PROMOTION_POLICY_GOVERNANCE.md``; labels are heuristic, not formal guarantees.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any

EPS_VEL = 1e-9
OSCILLATION_AMPLITUDE_BAND_DEFAULT = 0.2
M_AS_SCALE = 0.05
A_AS_SCALE = 1.0


def iter_history_dicts(lines: list[str]) -> Any:
    """Yield (line_index, row) for each valid JSON object line, in file order."""
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield i, row


def build_contested_ma_trajectory(
    lines: list[str],
    *,
    max_points: int,
) -> list[dict[str, Any]]:
    """
    Chronological contested runs with M, A, S coordinates (file order).

    ``max_points`` > 0 keeps only the last N points; 0 = keep all.
    """
    pts: list[dict[str, Any]] = []
    run_idx = 0
    for ln, row in iter_history_dicts(lines):
        if row.get("decision_state") != "contested":
            continue
        m = row.get("external_margin_abs")
        a = row.get("external_metric_agreement_ratio")
        s = row.get("external_tie_break_streak")
        if not isinstance(m, (int, float)) or not isinstance(a, (int, float)) or not isinstance(s, int):
            continue
        pts.append(
            {
                "run_index": run_idx,
                "file_line_index": ln,
                "external_margin_abs": float(m),
                "external_metric_agreement_ratio": float(a),
                "external_tie_break_streak": int(s),
                "tie_break_confidence": row.get("tie_break_confidence"),
                "tie_break_reason": row.get("tie_break_reason"),
                "decision_state": row.get("decision_state"),
                "timestamp_utc": row.get("timestamp_utc"),
                "tie_break_confidence_threshold_effective": row.get("tie_break_confidence_threshold_effective"),
            }
        )
        run_idx += 1
    if max_points > 0 and len(pts) > max_points:
        pts = pts[-max_points:]
    for i, p in enumerate(pts):
        p["trajectory_index"] = i
    return pts


def contested_trajectory_plus_current(
    history_lines: list[str],
    *,
    current_row: dict[str, Any],
    history_tail_max_points: int,
) -> list[dict[str, Any]]:
    """History contested M–A–S trajectory plus one synthetic current row (for stability gate)."""
    base = build_contested_ma_trajectory(history_lines, max_points=history_tail_max_points)
    cur = dict(current_row)
    cur["trajectory_index"] = len(base)
    cur["run_index"] = len(base)
    base.append(cur)
    return base


def _effective_threshold_for_row(row: dict[str, Any], fallback: float) -> float:
    t = row.get("tie_break_confidence_threshold_effective")
    if isinstance(t, (int, float)):
        return float(t)
    return float(fallback)


def enrich_trajectory_with_threshold_distance(
    trajectory: list[dict[str, Any]],
    *,
    threshold_fallback: float,
) -> list[dict[str, Any]]:
    """Add per-point ``confidence_distance_to_threshold`` using row effective threshold or fallback."""
    out: list[dict[str, Any]] = []
    for p in trajectory:
        q = dict(p)
        thr = _effective_threshold_for_row(q, threshold_fallback)
        q["effective_threshold_used"] = thr
        tc = q.get("tie_break_confidence")
        if isinstance(tc, (int, float)):
            q["confidence_distance_to_threshold"] = float(tc) - thr
        else:
            q["confidence_distance_to_threshold"] = None
        out.append(q)
    return out


def augment_trajectory_dynamics(
    trajectory: list[dict[str, Any]],
    *,
    near_boundary_epsilon: float,
) -> list[dict[str, Any]]:
    """
    Per contested trajectory point (after distance enrichment):

    ``trajectory_blocking_reason``, ``blocking_reason_streak``, ``confidence_velocity``,
    ``normalized_confidence_velocity``, ``confidence_acceleration``, ``near_boundary_streak``.
    """
    out: list[dict[str, Any]] = []
    band_streak = 0
    reason_streak = 0
    prev_reason: str | None = None
    prev_d: float | None = None
    prev_v: float | None = None
    for p in trajectory:
        q = dict(p)
        tr = q.get("tie_break_reason")
        q["trajectory_blocking_reason"] = tr if isinstance(tr, str) else None
        if isinstance(tr, str):
            if prev_reason is not None and tr == prev_reason:
                reason_streak += 1
            else:
                reason_streak = 1
            prev_reason = tr
        else:
            reason_streak = 0
            prev_reason = None
        q["blocking_reason_streak"] = reason_streak if isinstance(tr, str) else 0

        d_raw = q.get("confidence_distance_to_threshold")
        if isinstance(d_raw, (int, float)):
            d = float(d_raw)
            if abs(d) < near_boundary_epsilon:
                band_streak += 1
            else:
                band_streak = 0
            q["near_boundary_streak"] = band_streak

            if prev_d is not None:
                v = d - prev_d
                q["confidence_velocity"] = v
                q["normalized_confidence_velocity"] = v / (abs(prev_d) + EPS_VEL)
                if prev_v is not None:
                    q["confidence_acceleration"] = v - prev_v
                else:
                    q["confidence_acceleration"] = None
                prev_v = v
            else:
                q["confidence_velocity"] = None
                q["normalized_confidence_velocity"] = None
                q["confidence_acceleration"] = None
                prev_v = None
            prev_d = d
        else:
            band_streak = 0
            q["near_boundary_streak"] = 0
            q["confidence_velocity"] = None
            q["normalized_confidence_velocity"] = None
            q["confidence_acceleration"] = None
            prev_d = None
            prev_v = None
        out.append(q)
    return out


def add_approach_vectors(
    trajectory: list[dict[str, Any]],
    *,
    streak_scale: float = 3.0,
) -> list[dict[str, Any]]:
    """
    Per step: ``approach_delta_mas`` = Δ(M, A, S) vs previous point;
    ``alignment_with_promotion_direction`` = cosine similarity of scaled Δ with (1,1,1) direction (heuristic).
    """
    out: list[dict[str, Any]] = []
    prev: dict[str, Any] | None = None
    for p in trajectory:
        q = dict(p)
        if prev is not None:
            dm = float(q["external_margin_abs"]) - float(prev["external_margin_abs"])
            da = float(q["external_metric_agreement_ratio"]) - float(prev["external_metric_agreement_ratio"])
            ds = float(int(q["external_tie_break_streak"]) - int(prev["external_tie_break_streak"]))
            q["approach_delta_mas"] = [dm, da, ds]
            vn = (dm / M_AS_SCALE, da / A_AS_SCALE, ds / streak_scale)
            norm = math.sqrt(vn[0] ** 2 + vn[1] ** 2 + vn[2] ** 2)
            inv_sqrt3 = 1.0 / math.sqrt(3.0)
            ref = (inv_sqrt3, inv_sqrt3, inv_sqrt3)
            dot = sum(vn[i] * ref[i] for i in range(3))
            if norm > 1e-12:
                q["alignment_with_promotion_direction"] = dot / norm
            else:
                q["alignment_with_promotion_direction"] = None
        else:
            q["approach_delta_mas"] = None
            q["alignment_with_promotion_direction"] = None
        out.append(q)
        prev = q
    return out


def boundary_crossings_from_trajectory(
    trajectory_enriched: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Sign changes of (confidence - effective_threshold) between consecutive contested trajectory points
    that both recorded numeric ``tie_break_confidence``.
    """
    crossings: list[dict[str, Any]] = []
    seq = trajectory_enriched
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        ca = a.get("tie_break_confidence")
        cb = b.get("tie_break_confidence")
        if not isinstance(ca, (int, float)) or not isinstance(cb, (int, float)):
            continue
        tha = float(a.get("effective_threshold_used", 0.0))
        thb = float(b.get("effective_threshold_used", 0.0))
        da = float(ca) - tha
        db = float(cb) - thb
        if da * db >= 0:
            continue
        crossings.append(
            {
                "between_trajectory_index": i,
                "from": {
                    "trajectory_index": a.get("trajectory_index"),
                    "file_line_index": a.get("file_line_index"),
                    "tie_break_confidence": float(ca),
                    "effective_threshold_used": tha,
                    "confidence_distance_to_threshold": da,
                    "timestamp_utc": a.get("timestamp_utc"),
                },
                "to": {
                    "trajectory_index": b.get("trajectory_index"),
                    "file_line_index": b.get("file_line_index"),
                    "tie_break_confidence": float(cb),
                    "effective_threshold_used": thb,
                    "confidence_distance_to_threshold": db,
                    "timestamp_utc": b.get("timestamp_utc"),
                },
                "direction": "up" if db > da else "down",
            }
        )
    return crossings


def _oscillation_like(
    boundary_crossings: list[dict[str, Any]],
    ds: list[float],
) -> bool:
    if len(boundary_crossings) >= 2:
        return True
    signs: list[int] = []
    for x in ds:
        if x > 1e-12:
            signs.append(1)
        elif x < -1e-12:
            signs.append(-1)
        else:
            signs.append(0)
    flips = 0
    for i in range(len(signs) - 1):
        if signs[i] != 0 and signs[i + 1] != 0 and signs[i] * signs[i + 1] < 0:
            flips += 1
    return flips >= 2


def classify_trajectory_basin(
    trajectory: list[dict[str, Any]],
    *,
    boundary_crossings: list[dict[str, Any]],
    oscillation_amplitude_band: float = OSCILLATION_AMPLITUDE_BAND_DEFAULT,
) -> str:
    """
    Heuristic label for the contested-only trajectory (not a formal stability proof).

    ``oscillation_amplitude_band``: if oscillation-like and max(|distance|) exceeds this, label as
    ``large_swing_instability`` instead of ``oscillating_boundary``.
    """
    ds: list[float] = []
    for p in trajectory:
        d = p.get("confidence_distance_to_threshold")
        if isinstance(d, (int, float)):
            ds.append(float(d))
    if len(ds) < 2:
        return "insufficient_history"

    max_abs = max(abs(x) for x in ds)
    osc = _oscillation_like(boundary_crossings, ds)
    if osc:
        if max_abs <= oscillation_amplitude_band:
            return "oscillating_boundary"
        return "large_swing_instability"

    if all(x < -0.1 for x in ds):
        return "stuck_low_signal"

    delta = ds[-1] - ds[0]
    if delta > 0.02:
        return "converging_to_promotion"
    if delta < -0.02:
        return "diverging_from_promotion"
    return "indeterminate"


def dominant_blocking_reason(trajectory: list[dict[str, Any]]) -> str | None:
    reasons = []
    for p in trajectory:
        r = p.get("trajectory_blocking_reason")
        if not isinstance(r, str):
            r = p.get("tie_break_reason")
        if isinstance(r, str):
            reasons.append(r)
    if not reasons:
        return None
    return Counter(reasons).most_common(1)[0][0]


def compute_stability_score(
    trajectory: list[dict[str, Any]],
    *,
    boundary_crossings: list[dict[str, Any]],
    near_boundary_epsilon: float,
) -> float | None:
    """
    Single scalar in [0, 1] (heuristic): higher ⇒ more stable-looking trajectory for CI summaries.

    ``1 - min(1, crossings/N) - min(1, var(velocity)) - 0.5 * near_boundary_fraction``
    """
    dists = [
        float(p["confidence_distance_to_threshold"])
        for p in trajectory
        if isinstance(p.get("confidence_distance_to_threshold"), (int, float))
    ]
    n = len(dists)
    if n < 1:
        return None
    k = len(boundary_crossings)
    term_cross = 1.0 - min(1.0, k / max(n, 1))

    velocities = [
        float(p["confidence_velocity"])
        for p in trajectory
        if isinstance(p.get("confidence_velocity"), (int, float))
    ]
    if len(velocities) >= 1:
        mean_v = sum(velocities) / len(velocities)
        var_v = sum((x - mean_v) ** 2 for x in velocities) / len(velocities)
    else:
        var_v = 0.0
    term_var = min(1.0, var_v)

    nb_count = sum(
        1
        for p in trajectory
        if isinstance(p.get("confidence_distance_to_threshold"), (int, float))
        and abs(float(p["confidence_distance_to_threshold"])) < near_boundary_epsilon
    )
    frac = nb_count / n
    term_nb = frac * 0.5

    score = term_cross - term_var - term_nb
    return max(0.0, min(1.0, score))


def trajectory_dynamics_summary_dict(
    trajectory: list[dict[str, Any]],
    *,
    near_boundary_epsilon: float,
    boundary_crossings: list[dict[str, Any]],
    oscillation_amplitude_band: float = OSCILLATION_AMPLITUDE_BAND_DEFAULT,
) -> dict[str, Any]:
    streaks = [p.get("near_boundary_streak") for p in trajectory]
    mx = 0
    for s in streaks:
        if isinstance(s, int):
            mx = max(mx, s)
    return {
        "near_boundary_epsilon": near_boundary_epsilon,
        "oscillation_amplitude_band": oscillation_amplitude_band,
        "max_near_boundary_streak": mx,
        "trajectory_dynamical_class": classify_trajectory_basin(
            trajectory,
            boundary_crossings=boundary_crossings,
            oscillation_amplitude_band=oscillation_amplitude_band,
        ),
        "dominant_blocking_reason": dominant_blocking_reason(trajectory),
        "stability_score": compute_stability_score(
            trajectory,
            boundary_crossings=boundary_crossings,
            near_boundary_epsilon=near_boundary_epsilon,
        ),
    }


def tie_break_stability_gate(
    history_lines: list[str],
    *,
    current_row: dict[str, Any],
    threshold_fallback: float,
    near_boundary_epsilon: float,
    require_upward_crossing: bool,
    max_abs_acceleration: float | None,
    max_near_boundary_streak: int | None,
    history_tail_max_points: int,
) -> tuple[bool, str | None]:
    """
    Optional guard when tie-break confidence clears threshold: block ``contested_external_override``
    on spike-like or dwell-heavy trajectories (heuristic).

    Returns ``(True, None)`` if the gate passes, else ``(False, reason_code)``.
    """
    traj = contested_trajectory_plus_current(
        history_lines,
        current_row=current_row,
        history_tail_max_points=history_tail_max_points,
    )
    traj = enrich_trajectory_with_threshold_distance(traj, threshold_fallback=threshold_fallback)
    traj = augment_trajectory_dynamics(traj, near_boundary_epsilon=near_boundary_epsilon)

    last = traj[-1]
    prev = traj[-2] if len(traj) >= 2 else None

    if require_upward_crossing:
        if prev is None:
            return False, "tie_break_stability_gate_missing_upward_crossing"
        pd_prev = prev.get("confidence_distance_to_threshold")
        pd_last = last.get("confidence_distance_to_threshold")
        if not isinstance(pd_prev, (int, float)) or not isinstance(pd_last, (int, float)):
            return False, "tie_break_stability_gate_missing_upward_crossing"
        if not (float(pd_prev) < 0 and float(pd_last) >= 0):
            return False, "tie_break_stability_gate_missing_upward_crossing"

    if max_abs_acceleration is not None:
        acc = last.get("confidence_acceleration")
        if isinstance(acc, (int, float)) and abs(float(acc)) > max_abs_acceleration:
            return False, "tie_break_stability_gate_high_acceleration"

    if max_near_boundary_streak is not None:
        nbs = last.get("near_boundary_streak")
        if isinstance(nbs, int) and nbs >= max_near_boundary_streak:
            return False, "tie_break_stability_gate_near_boundary_dwell"

    return True, None
