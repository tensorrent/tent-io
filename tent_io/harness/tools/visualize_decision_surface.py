#!/usr/bin/env python3
"""
Synthetic promotion / tie-break decision surface for diagnostics.

Sweeps margin, agreement, and tie-break streak using the same confidence weights and
gate ordering as ``compute_promotion_decision.py`` (see ``promotion_decision_logic.py``).

Outputs JSON suitable for CI artifacts; optional PNG (matplotlib) for local inspection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from promotion_decision_logic import (  # noqa: E402
    adaptive_effective_threshold,
    contested_tie_break_confidences_from_history_lines,
    tie_break_confidence,
)
from trajectory_dynamics import (  # noqa: E402
    add_approach_vectors,
    augment_trajectory_dynamics,
    boundary_crossings_from_trajectory,
    build_contested_ma_trajectory,
    enrich_trajectory_with_threshold_distance,
    trajectory_dynamics_summary_dict,
)


def margin_consistent_with_favor(favored: str, margin_signed: float | None, eps: float = 1e-9) -> bool:
    if margin_signed is None:
        return False
    if favored == "expand_s1":
        return margin_signed > eps
    if favored == "expand_s2":
        return margin_signed < -eps
    return False


def signed_margin_for_favor(favored: str, margin_abs: float) -> float | None:
    if favored == "expand_s1":
        return float(margin_abs)
    if favored == "expand_s2":
        return -float(margin_abs)
    return None


def linspace(lo: float, hi: float, n: int) -> list[float]:
    if n < 2:
        return [lo]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def irange(lo: int, hi: int) -> list[int]:
    return list(range(lo, hi + 1))


def evaluate_tie_break_cell(
    *,
    margin_abs: float,
    agreement_ratio: float,
    tb_streak: int,
    favored: str,
    agreement_floor: float,
    margin_floor: float,
    effective_threshold: float,
    streak_required: int,
    target_margin: float,
    best_profile: dict[str, Any],
    relax_drift: bool,
    drift_tol: float,
) -> dict[str, Any]:
    """Mirror contested tie-break branch (floors → confidence → threshold)."""
    margin_signed = signed_margin_for_favor(favored, margin_abs)
    conf: float | None = None
    components: dict[str, float] = {}

    if agreement_ratio < agreement_floor:
        tie_break_reason = "low_metric_agreement"
        decision_state = "contested"
    elif margin_abs < margin_floor:
        tie_break_reason = "margin_too_small"
        decision_state = "contested"
    elif not margin_consistent_with_favor(favored, margin_signed):
        tie_break_reason = "aggregate_margin_sign_mismatch"
        decision_state = "contested"
    else:
        conf, components = tie_break_confidence(
            margin_abs=margin_abs,
            tb_streak=tb_streak,
            streak_required=streak_required,
            agreement_ratio=agreement_ratio,
            best_profile=best_profile,
            relax_drift=relax_drift,
            target_margin=target_margin,
            drift_tol=drift_tol,
        )
        if conf >= effective_threshold:
            tie_break_reason = "tie_break_confidence_threshold_met"
            decision_state = "contested_external_override"
        else:
            tie_break_reason = "tie_break_confidence_below_effective_threshold"
            decision_state = "contested"

    promotion_allowed = decision_state == "contested_external_override"

    out: dict[str, Any] = {
        "margin_abs": margin_abs,
        "agreement_ratio": agreement_ratio,
        "external_tie_break_streak": tb_streak,
        "external_favored_slot": favored,
        "decision_state": decision_state,
        "promotion_allowed": promotion_allowed,
        "tie_break_reason": tie_break_reason,
        "tie_break_confidence": conf,
        "tie_break_confidence_components": components,
        "tie_break_confidence_threshold_effective": effective_threshold,
    }
    return out


def evaluate_aligned_cell(
    *,
    aligned_streak: int,
    internal_margin: float,
    alignment_required_runs: int,
    min_internal_margin: float,
    ext_vote_margin: int,
    min_external_vote_margin: int,
) -> dict[str, Any]:
    """Synthetic aligned path (slots agree); no tie-break."""
    meets_int = internal_margin >= min_internal_margin
    meets_ext = ext_vote_margin >= min_external_vote_margin
    if aligned_streak < alignment_required_runs:
        state = "aligned_pending_confirmation"
    elif not (meets_int and meets_ext):
        state = "aligned_but_margin_insufficient"
    else:
        state = "aligned_ready_for_promotion"
    return {
        "aligned_streak": aligned_streak,
        "internal_margin": internal_margin,
        "decision_state": state,
        "promotion_allowed": state == "aligned_ready_for_promotion",
    }


def load_history_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def history_overlay_points(
    lines: list[str],
    *,
    max_points: int,
) -> list[dict[str, Any]]:
    """Pull contested rows with usable coordinates for M–A–S overlay (last ``max_points``)."""
    pts = build_contested_ma_trajectory(lines, max_points=0)
    if max_points > 0 and len(pts) > max_points:
        return pts[-max_points:]
    return pts


def build_blocking_reason_ma_slice(
    cells: list[dict[str, Any]],
    *,
    streak: int,
    margin_values: list[float],
    agreement_values: list[float],
) -> dict[str, Any]:
    """2D grid of dominant ``tie_break_reason`` at fixed tie-break streak (same layout as confidence PNG)."""
    m_index = {round(v, 12): i for i, v in enumerate(margin_values)}
    a_index = {round(v, 12): i for i, v in enumerate(agreement_values)}
    nc = len(margin_values)
    na = len(agreement_values)
    reasons: list[list[str | None]] = [[None for _ in range(nc)] for _ in range(na)]
    for c in cells:
        if int(c["external_tie_break_streak"]) != streak:
            continue
        mi = m_index.get(round(float(c["margin_abs"]), 12))
        ai = a_index.get(round(float(c["agreement_ratio"]), 12))
        if mi is None or ai is None:
            continue
        reasons[ai][mi] = str(c.get("tie_break_reason") or "")
    return {
        "streak": streak,
        "margin_values": margin_values,
        "agreement_values": agreement_values,
        "tie_break_reasons": reasons,
    }


def build_tie_break_grid(
    *,
    margin_values: list[float],
    agreement_values: list[float],
    streak_values: list[int],
    favored: str,
    agreement_floor: float,
    margin_floor: float,
    static_threshold: float,
    streak_required: int,
    target_margin: float,
    best_profile: dict[str, Any],
    relax_drift: bool,
    drift_tol: float,
    history_lines: list[str],
    adaptive: bool,
    adaptive_window: int,
    adaptive_percentile: float,
    adaptive_clamp_min: float,
    adaptive_clamp_max: float,
    adaptive_min_samples: int,
) -> tuple[list[dict[str, Any]], float, float | None]:
    hist = contested_tie_break_confidences_from_history_lines(history_lines, max_tail=adaptive_window)
    if adaptive:
        effective, adaptive_raw = adaptive_effective_threshold(
            static_threshold,
            historical_confidences=hist,
            percentile=adaptive_percentile,
            clamp_min=adaptive_clamp_min,
            clamp_max=adaptive_clamp_max,
            min_samples=adaptive_min_samples,
        )
    else:
        effective = static_threshold
        adaptive_raw = None

    cells: list[dict[str, Any]] = []
    for m in margin_values:
        for a in agreement_values:
            for s in streak_values:
                cells.append(
                    evaluate_tie_break_cell(
                        margin_abs=m,
                        agreement_ratio=a,
                        tb_streak=s,
                        favored=favored,
                        agreement_floor=agreement_floor,
                        margin_floor=margin_floor,
                        effective_threshold=effective,
                        streak_required=streak_required,
                        target_margin=target_margin,
                        best_profile=best_profile,
                        relax_drift=relax_drift,
                        drift_tol=drift_tol,
                    )
                )
    return cells, effective, adaptive_raw


def build_aligned_grid(
    *,
    streak_values: list[int],
    internal_margin_values: list[float],
    alignment_required_runs: int,
    min_internal_margin: float,
    ext_vote_margin: int,
    min_external_vote_margin: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for st in streak_values:
        for im in internal_margin_values:
            row = evaluate_aligned_cell(
                aligned_streak=st,
                internal_margin=im,
                alignment_required_runs=alignment_required_runs,
                min_internal_margin=min_internal_margin,
                ext_vote_margin=ext_vote_margin,
                min_external_vote_margin=min_external_vote_margin,
            )
            out.append(row)
    return out


def _pivot_tie_break_slice(
    cells: list[dict[str, Any]],
    *,
    streak: int,
    margin_values: list[float],
    agreement_values: list[float],
) -> tuple[list[list[float]], list[list[str]]]:
    """2D arrays [agreement][margin] to match imshow row = agreement."""
    m_index = {round(v, 12): i for i, v in enumerate(margin_values)}
    a_index = {round(v, 12): i for i, v in enumerate(agreement_values)}
    nc = len(margin_values)
    na = len(agreement_values)
    conf = [[float("nan") for _ in range(nc)] for _ in range(na)]
    state = [["" for _ in range(nc)] for _ in range(na)]
    for c in cells:
        if int(c["external_tie_break_streak"]) != streak:
            continue
        mi = m_index.get(round(float(c["margin_abs"]), 12))
        ai = a_index.get(round(float(c["agreement_ratio"]), 12))
        if mi is None or ai is None:
            continue
        tc = c.get("tie_break_confidence")
        if isinstance(tc, (int, float)):
            conf[ai][mi] = float(tc)
        state[ai][mi] = str(c.get("decision_state", ""))
    return conf, state


def _reason_category_ids(
    reasons_grid: list[list[str | None]],
) -> tuple[list[list[float]], list[str]]:
    """Map reason strings to float codes for imshow; None → nan."""
    flat: set[str] = set()
    for row in reasons_grid:
        for r in row:
            if r:
                flat.add(r)
    ordered = sorted(flat)
    rmap = {r: float(i) for i, r in enumerate(ordered)}
    out: list[list[float]] = []
    for row in reasons_grid:
        out.append([float("nan") if not x else rmap[x] for x in row])
    return out, ordered


def render_png(
    *,
    png_path: Path,
    cells: list[dict[str, Any]],
    margin_values: list[float],
    agreement_values: list[float],
    streak_slice: int,
    effective_threshold: float,
    static_threshold: float,
    overlay: list[dict[str, Any]] | None,
    trajectory_enriched: list[dict[str, Any]] | None,
    blocking_reason_slice: dict[str, Any] | None,
    include_blocking_panel: bool,
    title: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap

    conf_grid, _ = _pivot_tie_break_slice(
        cells,
        streak=streak_slice,
        margin_values=margin_values,
        agreement_values=agreement_values,
    )
    arr = np.array(conf_grid, dtype=float)
    extent = [
        margin_values[0],
        margin_values[-1],
        agreement_values[0],
        agreement_values[-1],
    ]

    n_panels = 2 if (include_blocking_panel and blocking_reason_slice) else 1
    fig, axes = plt.subplots(n_panels, 1, figsize=(8, 5.5 * n_panels))
    if n_panels == 1:
        axes = [axes]

    ax = axes[0]
    im = ax.imshow(
        arr,
        origin="lower",
        extent=[extent[0], extent[1], extent[2], extent[3]],
        aspect="auto",
        cmap="viridis",
        vmin=0.0,
        vmax=1.0,
    )
    M, A = np.meshgrid(np.asarray(margin_values, dtype=float), np.asarray(agreement_values, dtype=float))
    try:
        ax.contour(
            M,
            A,
            arr,
            levels=[effective_threshold],
            colors="white",
            linewidths=1.2,
            linestyles="solid",
        )
    except ValueError:
        pass
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("tie_break_confidence")
    ax.set_xlabel("|aggregate external margin|")
    ax.set_ylabel("metric agreement ratio (favored direction)")
    ax.set_title(title + f"\n(streak={streak_slice}, eff_thr={effective_threshold:.3f}, static={static_threshold:.3f})")

    traj = trajectory_enriched or []
    traj_s = [p for p in traj if int(p.get("external_tie_break_streak", -1)) == streak_slice]
    if len(traj_s) >= 2:
        xs = [p["external_margin_abs"] for p in traj_s]
        ys = [p["external_metric_agreement_ratio"] for p in traj_s]
        ax.plot(xs, ys, color="white", alpha=0.45, linewidth=1.2, linestyle="-", label="trajectory (time order)")
    if traj_s:
        ntr = len(traj_s)
        for k, p in enumerate(traj_s):
            tnorm = k / max(1, ntr - 1)
            ax.scatter(
                [p["external_margin_abs"]],
                [p["external_metric_agreement_ratio"]],
                s=22 + k * 2,
                color=plt.cm.coolwarm(tnorm),
                edgecolors="black",
                linewidths=0.35,
                zorder=5,
            )
        ax.scatter([], [], color=plt.cm.coolwarm(0.5), s=30, edgecolors="black", label="runs (color/size → time)")
    elif overlay:
        xs = [p["external_margin_abs"] for p in overlay if int(p.get("external_tie_break_streak", -1)) == streak_slice]
        ys = [p["external_metric_agreement_ratio"] for p in overlay if int(p.get("external_tie_break_streak", -1)) == streak_slice]
        if xs:
            ax.scatter(xs, ys, s=22, c="red", edgecolors="black", linewidths=0.4, label="history (contested)")
    _handles, leg_labels = ax.get_legend_handles_labels()
    if leg_labels:
        ax.legend(loc="upper left", fontsize=7)

    if n_panels == 2 and blocking_reason_slice:
        ax2 = axes[1]
        rgrid = blocking_reason_slice.get("tie_break_reasons") or []
        rid, labels = _reason_category_ids(rgrid)
        rarr = np.array(rid, dtype=float)
        nlab = max(1, len(labels))
        cmap2 = ListedColormap(plt.cm.tab20(np.linspace(0, 1, min(20, max(nlab, 1)))))
        im2 = ax2.imshow(
            rarr,
            origin="lower",
            extent=[extent[0], extent[1], extent[2], extent[3]],
            aspect="auto",
            cmap=cmap2,
            vmin=-0.5,
            vmax=max(nlab - 0.5, 0.5),
            interpolation="nearest",
        )
        ax2.set_xlabel("|aggregate external margin|")
        ax2.set_ylabel("metric agreement ratio (favored direction)")
        ax2.set_title("Dominant tie_break_reason (synthetic grid)")
        if labels:
            cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04, ticks=list(range(len(labels))))
            cbar2.ax.set_yticklabels(labels, fontsize=7)
        else:
            fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)

        if len(traj_s) >= 2:
            ax2.plot(
                [p["external_margin_abs"] for p in traj_s],
                [p["external_metric_agreement_ratio"] for p in traj_s],
                color="black",
                alpha=0.5,
                linewidth=1.0,
            )
        if traj_s:
            n2 = len(traj_s)
            for k, p in enumerate(traj_s):
                tnorm = k / max(1, n2 - 1)
                ax2.scatter(
                    [p["external_margin_abs"]],
                    [p["external_metric_agreement_ratio"]],
                    s=26 + k * 2,
                    color=plt.cm.coolwarm(tnorm),
                    edgecolors="white",
                    linewidths=0.3,
                    zorder=5,
                )

    fig.tight_layout()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=150)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description="Visualize promotion tie-break decision surface (synthetic grid).")
    p.add_argument("--output", required=True, help="Write JSON grid to this path.")
    p.add_argument("--png", default="", help="Optional PNG path (requires matplotlib).")
    p.add_argument("--png-streak", type=int, default=-1, help="Streak slice for PNG (default: streak required).")

    p.add_argument("--margin-max", type=float, default=0.05)
    p.add_argument("--margin-steps", type=int, default=26)
    p.add_argument("--agreement-steps", type=int, default=21)
    p.add_argument("--streak-max", type=int, default=-1, help="Max tie-break streak in grid (default: streak required).")

    p.add_argument("--streak-required", type=int, default=3, help="Alias for --external-tie-break-streak-required.")
    p.add_argument("--external-tie-break-streak-required", type=int, default=None)
    p.add_argument("--target-margin", type=float, default=0.03)
    p.add_argument("--confidence-threshold", type=float, default=0.75)
    p.add_argument("--tie-break-agreement-floor", type=float, default=0.6)
    p.add_argument("--tie-break-margin-floor", type=float, default=0.01)
    p.add_argument("--favored-profile", choices=("expand_s1", "expand_s2"), default="expand_s1")
    p.add_argument("--tie-break-relax-drift-check", action="store_true")
    p.add_argument("--train-eval-drift", type=float, default=0.0)
    p.add_argument("--tie-break-drift-tol", type=float, default=1e-6)

    p.add_argument("--tie-break-adaptive-threshold", action="store_true")
    p.add_argument("--history", default="", help="NDJSON history path for adaptive threshold and/or overlay.")
    p.add_argument("--tie-break-adaptive-window", type=int, default=20)
    p.add_argument("--tie-break-adaptive-percentile", type=float, default=75.0)
    p.add_argument("--tie-break-adaptive-clamp-min", type=float, default=0.65)
    p.add_argument("--tie-break-adaptive-clamp-max", type=float, default=0.85)
    p.add_argument("--tie-break-adaptive-min-samples", type=int, default=3)
    p.add_argument("--overlay-max-points", type=int, default=50)
    p.add_argument(
        "--trajectory-max-points",
        type=int,
        default=500,
        help="Max contested M–A–S points in history_trajectory_contested JSON; 0 = entire file.",
    )
    p.add_argument(
        "--png-include-blocking-reason",
        action="store_true",
        help="Add second PNG panel: dominant tie_break_reason over (M, A) at the PNG streak slice.",
    )
    p.add_argument(
        "--near-boundary-epsilon",
        type=float,
        default=0.05,
        help="Band |confidence_distance_to_threshold| < ε for near_boundary_streak (default 0.05).",
    )
    p.add_argument(
        "--oscillation-amplitude-band",
        type=float,
        default=0.2,
        help="Max |distance| for oscillating_boundary vs large_swing_instability (default 0.2).",
    )

    p.add_argument("--include-aligned-slice", action="store_true")
    p.add_argument("--alignment-required-runs", type=int, default=2)
    p.add_argument("--min-internal-margin", type=float, default=0.005)
    p.add_argument("--min-external-vote-margin", type=int, default=1)
    p.add_argument("--aligned-ext-vote-margin", type=int, default=2, help="Synthetic external vote margin for aligned slice.")
    p.add_argument("--aligned-int-margin-max", type=float, default=0.05)
    p.add_argument("--aligned-int-margin-steps", type=int, default=26)
    p.add_argument("--aligned-streak-max", type=int, default=-1, help="Default: alignment_required + 2.")

    args = p.parse_args()

    streak_req = args.external_tie_break_streak_required
    if streak_req is None:
        streak_req = args.streak_required
    streak_max = args.streak_max if args.streak_max >= 0 else streak_req
    aligned_streak_max = args.aligned_streak_max
    if aligned_streak_max < 0:
        aligned_streak_max = args.alignment_required_runs + 2

    margin_values = linspace(0.0, args.margin_max, max(2, args.margin_steps))
    agreement_values = linspace(0.0, 1.0, max(2, args.agreement_steps))
    streak_values = irange(0, max(0, streak_max))

    hist_path = Path(args.history) if args.history else None
    history_lines = load_history_lines(hist_path) if hist_path else []
    overlay = history_overlay_points(history_lines, max_points=args.overlay_max_points) if hist_path else []

    best_profile: dict[str, Any] = {"train_eval_drift": float(args.train_eval_drift)}

    cells, effective_thr, adaptive_raw = build_tie_break_grid(
        margin_values=margin_values,
        agreement_values=agreement_values,
        streak_values=streak_values,
        favored=args.favored_profile,
        agreement_floor=args.tie_break_agreement_floor,
        margin_floor=args.tie_break_margin_floor,
        static_threshold=args.confidence_threshold,
        streak_required=streak_req,
        target_margin=args.target_margin,
        best_profile=best_profile,
        relax_drift=args.tie_break_relax_drift_check,
        drift_tol=args.tie_break_drift_tol,
        history_lines=history_lines,
        adaptive=args.tie_break_adaptive_threshold,
        adaptive_window=args.tie_break_adaptive_window,
        adaptive_percentile=args.tie_break_adaptive_percentile,
        adaptive_clamp_min=args.tie_break_adaptive_clamp_min,
        adaptive_clamp_max=args.tie_break_adaptive_clamp_max,
        adaptive_min_samples=args.tie_break_adaptive_min_samples,
    )

    png_streak = args.png_streak if args.png_streak >= 0 else streak_req

    traj_cap = args.trajectory_max_points if args.trajectory_max_points > 0 else 0
    trajectory_raw = (
        build_contested_ma_trajectory(history_lines, max_points=traj_cap) if hist_path else []
    )
    trajectory_enriched = enrich_trajectory_with_threshold_distance(
        trajectory_raw,
        threshold_fallback=effective_thr,
    )
    boundary_crossings = boundary_crossings_from_trajectory(trajectory_enriched)
    trajectory_enriched = augment_trajectory_dynamics(
        trajectory_enriched,
        near_boundary_epsilon=args.near_boundary_epsilon,
    )
    trajectory_enriched = add_approach_vectors(
        trajectory_enriched,
        streak_scale=float(max(1, streak_req)),
    )
    dynamics_summary = trajectory_dynamics_summary_dict(
        trajectory_enriched,
        near_boundary_epsilon=args.near_boundary_epsilon,
        boundary_crossings=boundary_crossings,
        oscillation_amplitude_band=args.oscillation_amplitude_band,
    )

    blocking_slice = build_blocking_reason_ma_slice(
        cells,
        streak=png_streak,
        margin_values=margin_values,
        agreement_values=agreement_values,
    )

    out: dict[str, Any] = {
        "meta": {
            "description": "Synthetic grid: contested external tie-break path with tie-break enabled.",
            "margin_range": [0.0, args.margin_max],
            "agreement_range": [0.0, 1.0],
            "streak_range": [0, streak_max],
            "external_tie_break_streak_required": streak_req,
            "tie_break_target_margin": args.target_margin,
            "tie_break_confidence_threshold_static": args.confidence_threshold,
            "tie_break_confidence_threshold_effective": effective_thr,
            "adaptive_confidence_threshold": adaptive_raw,
            "tie_break_adaptive_enabled": args.tie_break_adaptive_threshold,
            "tie_break_agreement_floor": args.tie_break_agreement_floor,
            "tie_break_margin_floor": args.tie_break_margin_floor,
            "favored_profile": args.favored_profile,
            "train_eval_drift": args.train_eval_drift,
            "tie_break_relax_drift_check": args.tie_break_relax_drift_check,
            "history_path": str(hist_path) if hist_path else None,
            "tie_break_blocking_reason_slice_streak": png_streak,
            "trajectory_max_points": args.trajectory_max_points,
            "trajectory_dynamics_summary": dynamics_summary,
        },
        "contested_tie_break_grid": cells,
        "history_overlay_contested": overlay,
        "history_trajectory_contested": trajectory_enriched,
        "tie_break_boundary_crossings": boundary_crossings,
        "tie_break_blocking_reason_slice": blocking_slice,
    }

    if args.include_aligned_slice:
        im_vals = linspace(0.0, args.aligned_int_margin_max, max(2, args.aligned_int_margin_steps))
        st_vals = irange(0, aligned_streak_max)
        out["aligned_path_grid"] = build_aligned_grid(
            streak_values=st_vals,
            internal_margin_values=im_vals,
            alignment_required_runs=args.alignment_required_runs,
            min_internal_margin=args.min_internal_margin,
            ext_vote_margin=args.aligned_ext_vote_margin,
            min_external_vote_margin=args.min_external_vote_margin,
        )

    outp = Path(args.output)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=2, ensure_ascii=True), encoding="utf-8")

    if args.png:
        try:
            render_png(
                png_path=Path(args.png),
                cells=cells,
                margin_values=margin_values,
                agreement_values=agreement_values,
                streak_slice=png_streak,
                effective_threshold=effective_thr,
                static_threshold=args.confidence_threshold,
                overlay=overlay if overlay else None,
                trajectory_enriched=trajectory_enriched if trajectory_enriched else None,
                blocking_reason_slice=blocking_slice if args.png_include_blocking_reason else None,
                include_blocking_panel=args.png_include_blocking_reason,
                title="Contested tie-break confidence",
            )
        except ImportError as e:
            print(f"matplotlib required for --png: {e}", file=sys.stderr)
            sys.exit(1)

    print(json.dumps({"wrote_json": str(outp), "png": args.png or None, "effective_threshold": effective_thr}, indent=2))


if __name__ == "__main__":
    main()
