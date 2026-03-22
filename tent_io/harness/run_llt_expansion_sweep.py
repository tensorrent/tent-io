#!/usr/bin/env python3
"""Run deterministic LLT expansion profiles through the production gate."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPANSION_REPORTS_DIR = REPO_ROOT / "tent_io" / "harness" / "reports" / "expansion"


PROFILE_CONFIGS: dict[str, dict[str, float | int]] = {
    "expand_s1": {
        "llt_epochs": 2,
        "llt_hidden_dim": 64,
        "llt_max_train": 1024,
        "llt_max_test": 512,
        "llt_min_test_acc": 0.20,
        "llt_min_eval_acc": 0.20,
        "llt_max_replay_drift": 1e-12,
    },
    "expand_s2": {
        "llt_epochs": 3,
        "llt_hidden_dim": 96,
        "llt_max_train": 2048,
        "llt_max_test": 512,
        "llt_min_test_acc": 0.20,
        "llt_min_eval_acc": 0.20,
        "llt_max_replay_drift": 1e-12,
    },
    "expand_s3": {
        "llt_epochs": 4,
        "llt_hidden_dim": 128,
        "llt_max_train": 4096,
        "llt_max_test": 1024,
        "llt_min_test_acc": 0.20,
        "llt_min_eval_acc": 0.20,
        "llt_max_replay_drift": 1e-12,
    },
    "expand_s4": {
        "llt_epochs": 5,
        "llt_hidden_dim": 160,
        "llt_max_train": 6144,
        "llt_max_test": 1024,
        "llt_min_test_acc": 0.20,
        "llt_min_eval_acc": 0.20,
        "llt_max_replay_drift": 1e-12,
    },
    "expand_s5": {
        "llt_epochs": 6,
        "llt_hidden_dim": 192,
        "llt_max_train": 8192,
        "llt_max_test": 1536,
        "llt_min_test_acc": 0.20,
        "llt_min_eval_acc": 0.20,
        "llt_max_replay_drift": 1e-12,
    },
}


PROFILE_ALIASES: dict[str, list[str]] = {
    "auto_top2": ["expand_s2", "expand_s4"],
    "auto_all": ["expand_s1", "expand_s2", "expand_s3", "expand_s4", "expand_s5"],
}


def parse_profiles(raw: str) -> list[str]:
    out: list[str] = []
    for token in [x.strip() for x in raw.split(",") if x.strip()]:
        if token in PROFILE_ALIASES:
            out.extend(PROFILE_ALIASES[token])
        else:
            out.append(token)
    if not out:
        raise ValueError("No profiles selected.")
    # Deduplicate while preserving order so aliases can be mixed with explicit values.
    deduped: list[str] = []
    for item in out:
        if item not in deduped:
            deduped.append(item)
    out = deduped
    unknown = [p for p in out if p not in PROFILE_CONFIGS]
    if unknown:
        valid = sorted(list(PROFILE_CONFIGS) + list(PROFILE_ALIASES))
        raise ValueError(f"Unknown profiles: {unknown}. Valid: {valid}")
    return out


def stage_gate(report: dict[str, Any], stage_name: str) -> dict[str, Any] | None:
    stages = report.get("stages")
    if not isinstance(stages, dict):
        return None
    stage = stages.get(stage_name)
    if not isinstance(stage, dict):
        return None
    gates = stage.get("gates")
    if isinstance(gates, dict):
        return gates
    return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def metric_from_train_gates(train_gates: dict[str, Any], rank_by: str) -> float:
    metric_map = {
        "final_test_acc": "final_test_acc",
        "mmlu_test_acc": "final_mmlu_test_acc",
        "conversational_logic_test_acc": "final_conversational_logic_test_acc",
    }
    raw = train_gates.get(metric_map[rank_by])
    return _as_float(raw) or -1.0


def ranking_key(result: dict[str, Any], rank_by: str) -> tuple[int, float, float, float, int, str]:
    rc = int(result.get("pipeline_rc", 1))
    train_gates = result.get("train_gates")
    replay_gates = result.get("replay_gates")
    drift_summary = result.get("llt_drift_summary")

    train_pass = False
    replay_pass = False
    drift_pass = False
    rank_metric = -1.0
    final_test_acc = -1.0
    drift_val = float("inf")

    if isinstance(train_gates, dict):
        train_pass = bool(train_gates.get("passes") is True)
        rank_metric = metric_from_train_gates(train_gates, rank_by)
        final_test_acc = _as_float(train_gates.get("final_test_acc")) or -1.0
    if isinstance(replay_gates, dict):
        replay_pass = bool(replay_gates.get("passes") is True)
    if isinstance(drift_summary, dict):
        drift_pass = bool(drift_summary.get("drift_passes") is True)
        drift_val = _as_float(drift_summary.get("train_eval_drift")) or float("inf")

    pass_count = int(train_pass) + int(replay_pass) + int(drift_pass)
    return (pass_count, rank_metric, final_test_acc, -drift_val, -rc, str(result.get("profile", "")))


def append_ndjson(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def load_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except Exception:
            continue
    return rows


def ascii_sparkline(values: list[float]) -> str:
    if not values:
        return ""
    levels = "._-:=+*#%@"
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        mid = levels[len(levels) // 2]
        return mid * len(values)
    out: list[str] = []
    span = hi - lo
    max_idx = len(levels) - 1
    for value in values:
        idx = int(round(((value - lo) / span) * max_idx))
        if idx < 0:
            idx = 0
        if idx > max_idx:
            idx = max_idx
        out.append(levels[idx])
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LLT expansion profiles via production pipeline")
    parser.add_argument(
        "--profiles",
        default="expand_s1",
        help="Comma-separated profile names or aliases (auto_top2, auto_all).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=EXPANSION_REPORTS_DIR / "llt_expansion_sweep.current.json",
        help="Sweep summary JSON output.",
    )
    parser.add_argument(
        "--profile-reports-dir",
        type=Path,
        default=EXPANSION_REPORTS_DIR,
        help="Directory for per-profile pipeline reports.",
    )
    parser.add_argument(
        "--best-pointer-out",
        type=Path,
        default=EXPANSION_REPORTS_DIR / "llt_expansion_best.current.json",
        help="Rolling best-profile pointer JSON output.",
    )
    parser.add_argument("--llt-min-mmlu-test-acc", type=float, default=-1.0)
    parser.add_argument("--llt-min-conversational-test-acc", type=float, default=-1.0)
    parser.add_argument("--llt-min-eval-mmlu-acc", type=float, default=-1.0)
    parser.add_argument("--llt-min-eval-conversational-acc", type=float, default=-1.0)
    parser.add_argument(
        "--summary-md-out",
        type=Path,
        default=EXPANSION_REPORTS_DIR / "llt_expansion_sweep.current.md",
        help="Human-readable markdown summary output.",
    )
    parser.add_argument(
        "--history-out",
        type=Path,
        default=EXPANSION_REPORTS_DIR / "llt_expansion_history.ndjson",
        help="Append-only NDJSON history of sweep-level best profile metrics.",
    )
    parser.add_argument(
        "--trend-window",
        type=int,
        default=10,
        help="Number of recent sweep points to include in markdown trend section.",
    )
    parser.add_argument("--query", default="system profile check")
    parser.add_argument(
        "--rank-by",
        choices=["final_test_acc", "mmlu_test_acc", "conversational_logic_test_acc"],
        default="mmlu_test_acc",
        help="Ranking metric used after gate pass count.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate profile selection and exit without running sweeps.",
    )
    args = parser.parse_args()

    profiles = parse_profiles(args.profiles)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "validate_only": True,
                    "profiles_resolved": profiles,
                    "rank_by": args.rank_by,
                    "available_profiles": sorted(PROFILE_CONFIGS),
                    "available_aliases": PROFILE_ALIASES,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    root = REPO_ROOT
    run_started = datetime.now(timezone.utc)
    sweep_run_id = run_started.strftime("%Y%m%dT%H%M%S") + f"{run_started.microsecond // 1000:03d}Z"

    args.profile_reports_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    overall_rc = 0

    for profile in profiles:
        cfg = PROFILE_CONFIGS[profile]
        profile_report = args.profile_reports_dir / f"full_stage_pipeline.{profile}.{sweep_run_id}.json"
        cmd = [
            "python3",
            "tent_io/harness/run_full_stage_pipeline.py",
            "--production",
            "--query",
            args.query,
            "--out",
            str(profile_report),
            "--llt-epochs",
            str(int(cfg["llt_epochs"])),
            "--llt-hidden-dim",
            str(int(cfg["llt_hidden_dim"])),
            "--llt-max-train",
            str(int(cfg["llt_max_train"])),
            "--llt-max-test",
            str(int(cfg["llt_max_test"])),
            "--llt-min-test-acc",
            str(float(cfg["llt_min_test_acc"])),
            "--llt-min-eval-acc",
            str(float(cfg["llt_min_eval_acc"])),
            "--llt-max-replay-drift",
            str(float(cfg["llt_max_replay_drift"])),
            "--llt-min-mmlu-test-acc",
            str(args.llt_min_mmlu_test_acc),
            "--llt-min-conversational-test-acc",
            str(args.llt_min_conversational_test_acc),
            "--llt-min-eval-mmlu-acc",
            str(args.llt_min_eval_mmlu_acc),
            "--llt-min-eval-conversational-acc",
            str(args.llt_min_eval_conversational_acc),
        ]
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
        rc = int(proc.returncode)
        if rc != 0 and overall_rc == 0:
            overall_rc = rc

        payload: dict[str, Any] = {}
        if profile_report.exists():
            try:
                with profile_report.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    payload = loaded
            except Exception:
                payload = {}

        drift_summary = payload.get("llt_drift_summary") if isinstance(payload.get("llt_drift_summary"), dict) else None
        train_gates = stage_gate(payload, "train_liquid_language_model")
        replay_gates = stage_gate(payload, "eval_liquid_language_model_best")
        results.append(
            {
                "profile": profile,
                "config": cfg,
                "pipeline_rc": rc,
                "pipeline_status": payload.get("status"),
                "pipeline_report": str(profile_report),
                "run_id": payload.get("run_id"),
                "train_gates": train_gates,
                "replay_gates": replay_gates,
                "llt_drift_summary": drift_summary,
                "stdout_tail": proc.stdout[-500:],
                "stderr_tail": proc.stderr[-500:],
            }
        )

    ranked = sorted(results, key=lambda item: ranking_key(item, args.rank_by), reverse=True)
    ranking: list[dict[str, Any]] = []
    for i, item in enumerate(ranked, start=1):
        train_gates = item.get("train_gates") if isinstance(item.get("train_gates"), dict) else {}
        replay_gates = item.get("replay_gates") if isinstance(item.get("replay_gates"), dict) else {}
        drift_summary = item.get("llt_drift_summary") if isinstance(item.get("llt_drift_summary"), dict) else {}
        ranking.append(
            {
                "rank": i,
                "profile": item.get("profile"),
                "pipeline_rc": item.get("pipeline_rc"),
                "pipeline_status": item.get("pipeline_status"),
                "final_test_acc": _as_float(train_gates.get("final_test_acc")),
                "final_mmlu_test_acc": _as_float(train_gates.get("final_mmlu_test_acc")),
                "final_conversational_logic_test_acc": _as_float(train_gates.get("final_conversational_logic_test_acc")),
                "replay_test_acc": _as_float(replay_gates.get("test_acc")),
                "replay_mmlu_test_acc": _as_float(replay_gates.get("mmlu_test_acc")),
                "replay_conversational_logic_test_acc": _as_float(replay_gates.get("conversational_logic_test_acc")),
                "train_eval_drift": _as_float(drift_summary.get("train_eval_drift")),
                "train_gate_passes": _as_bool(train_gates.get("passes")),
                "replay_gate_passes": _as_bool(replay_gates.get("passes")),
                "drift_passes": _as_bool(drift_summary.get("drift_passes")),
                "rank_by": args.rank_by,
                "rank_metric_value": metric_from_train_gates(train_gates, args.rank_by),
            }
        )

    best_profile = ranking[0] if ranking else None
    summary: dict[str, Any] = {
        "sweep_run_id": sweep_run_id,
        "timestamp_utc": run_started.isoformat().replace("+00:00", "Z"),
        "profiles": profiles,
        "rank_by": args.rank_by,
        "split_gates": {
            "llt_min_mmlu_test_acc": args.llt_min_mmlu_test_acc,
            "llt_min_conversational_test_acc": args.llt_min_conversational_test_acc,
            "llt_min_eval_mmlu_acc": args.llt_min_eval_mmlu_acc,
            "llt_min_eval_conversational_acc": args.llt_min_eval_conversational_acc,
        },
        "status": "ok" if overall_rc == 0 else "partial_or_failed",
        "best_profile": best_profile,
        "ranking": ranking,
        "results": results,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=True)

    pointer: dict[str, Any] = {
        "timestamp_utc": run_started.isoformat().replace("+00:00", "Z"),
        "sweep_run_id": sweep_run_id,
        "summary_path": str(args.out),
        "profiles": profiles,
        "rank_by": args.rank_by,
        "best_profile": best_profile,
        "status": summary["status"],
    }
    args.best_pointer_out.parent.mkdir(parents=True, exist_ok=True)
    with args.best_pointer_out.open("w", encoding="utf-8") as f:
        json.dump(pointer, f, indent=2, ensure_ascii=True)

    history_row = {
        "timestamp_utc": run_started.isoformat().replace("+00:00", "Z"),
        "sweep_run_id": sweep_run_id,
        "profiles": profiles,
        "status": summary["status"],
        "rank_by": args.rank_by,
        "best_profile": best_profile.get("profile") if isinstance(best_profile, dict) else None,
        "best_final_test_acc": best_profile.get("final_test_acc") if isinstance(best_profile, dict) else None,
        "best_rank_metric_value": best_profile.get("rank_metric_value") if isinstance(best_profile, dict) else None,
        "best_replay_test_acc": best_profile.get("replay_test_acc") if isinstance(best_profile, dict) else None,
        "best_train_eval_drift": best_profile.get("train_eval_drift") if isinstance(best_profile, dict) else None,
    }
    append_ndjson(args.history_out, history_row)
    history_rows = load_ndjson(args.history_out)
    window = args.trend_window if args.trend_window > 0 else 1
    recent_rows = history_rows[-window:]
    recent_accs: list[float] = []
    for row in recent_rows:
        val = _as_float(row.get("best_rank_metric_value"))
        if val is not None:
            recent_accs.append(val)
    trend = {
        "history_path": str(args.history_out),
        "rank_by": args.rank_by,
        "window": window,
        "points": len(recent_rows),
        "valid_metric_points": len(recent_accs),
        "sparkline_ascii": ascii_sparkline(recent_accs),
        "min_metric": min(recent_accs) if recent_accs else None,
        "max_metric": max(recent_accs) if recent_accs else None,
        "last_metric": recent_accs[-1] if recent_accs else None,
    }
    summary["trend"] = trend
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=True)

    md_lines: list[str] = []
    md_lines.append("# LLT Expansion Sweep")
    md_lines.append("")
    md_lines.append(f"- sweep_run_id: `{sweep_run_id}`")
    md_lines.append(f"- timestamp_utc: `{run_started.isoformat().replace('+00:00', 'Z')}`")
    md_lines.append(f"- status: `{summary['status']}`")
    md_lines.append(f"- profiles: `{','.join(profiles)}`")
    md_lines.append(f"- rank_by: `{args.rank_by}`")
    md_lines.append(
        "- split_gates: "
        f"`train_mmlu={args.llt_min_mmlu_test_acc}, train_conv={args.llt_min_conversational_test_acc}, "
        f"eval_mmlu={args.llt_min_eval_mmlu_acc}, eval_conv={args.llt_min_eval_conversational_acc}`"
    )
    md_lines.append("")
    if isinstance(best_profile, dict):
        md_lines.append("## Best Profile")
        md_lines.append("")
        md_lines.append(f"- profile: `{best_profile.get('profile')}`")
        md_lines.append(f"- rank_metric_value: `{best_profile.get('rank_metric_value')}`")
        md_lines.append(f"- final_test_acc: `{best_profile.get('final_test_acc')}`")
        md_lines.append(f"- final_mmlu_test_acc: `{best_profile.get('final_mmlu_test_acc')}`")
        md_lines.append(f"- final_conversational_logic_test_acc: `{best_profile.get('final_conversational_logic_test_acc')}`")
        md_lines.append(f"- replay_test_acc: `{best_profile.get('replay_test_acc')}`")
        md_lines.append(f"- replay_mmlu_test_acc: `{best_profile.get('replay_mmlu_test_acc')}`")
        md_lines.append(f"- replay_conversational_logic_test_acc: `{best_profile.get('replay_conversational_logic_test_acc')}`")
        md_lines.append(f"- train_eval_drift: `{best_profile.get('train_eval_drift')}`")
        md_lines.append("")
    md_lines.append("## Trend (Recent Best Ranking Metric)")
    md_lines.append("")
    md_lines.append(f"- history_path: `{args.history_out}`")
    md_lines.append(f"- rank_by: `{trend['rank_by']}`")
    md_lines.append(f"- window: `{trend['window']}`")
    md_lines.append(f"- points: `{trend['points']}`")
    md_lines.append(f"- valid_metric_points: `{trend['valid_metric_points']}`")
    md_lines.append(f"- min_metric: `{trend['min_metric']}`")
    md_lines.append(f"- max_metric: `{trend['max_metric']}`")
    md_lines.append(f"- last_metric: `{trend['last_metric']}`")
    md_lines.append(f"- sparkline_ascii: `{trend['sparkline_ascii']}`")
    md_lines.append("")
    md_lines.append("## Ranking")
    md_lines.append("")
    md_lines.append("| rank | profile | rank_metric_value | final_test_acc | final_mmlu | final_conv | replay_test_acc | drift | train_gate | replay_gate | drift_gate |")
    md_lines.append("|---:|---|---:|---:|---:|---:|---:|---:|:---:|:---:|:---:|")
    for row in ranking:
        md_lines.append(
            "| {rank} | {profile} | {rank_metric_value} | {final_test_acc} | {final_mmlu_test_acc} | {final_conversational_logic_test_acc} | {replay_test_acc} | {train_eval_drift} | {train_gate_passes} | {replay_gate_passes} | {drift_passes} |".format(
                rank=row.get("rank"),
                profile=row.get("profile"),
                rank_metric_value=row.get("rank_metric_value"),
                final_test_acc=row.get("final_test_acc"),
                final_mmlu_test_acc=row.get("final_mmlu_test_acc"),
                final_conversational_logic_test_acc=row.get("final_conversational_logic_test_acc"),
                replay_test_acc=row.get("replay_test_acc"),
                train_eval_drift=row.get("train_eval_drift"),
                train_gate_passes=row.get("train_gate_passes"),
                replay_gate_passes=row.get("replay_gate_passes"),
                drift_passes=row.get("drift_passes"),
            )
        )
    args.summary_md_out.parent.mkdir(parents=True, exist_ok=True)
    with args.summary_md_out.open("w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(json.dumps({"out": str(args.out), "status": summary["status"]}, indent=2, ensure_ascii=True))
    return overall_rc


if __name__ == "__main__":
    raise SystemExit(main())
