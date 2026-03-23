#!/usr/bin/env python3
"""
Aggregate internal harness metrics and run lightweight benchmark lanes that exist in-repo.

This is a status snapshot, not a claim of parity with frontier API benchmarks.
See tent_io/docs/INTELLIGENCE_BENCHMARK_STATUS_AND_PLAN.md for interpretation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_HARNESS_DIR = Path(__file__).resolve().parent.parent
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))
from cli_inference_harness import cli_binary_configured, resolve_cli_binary_from_env  # noqa: E402


def repo_root() -> Path:
    # tools/ -> harness/ -> tent_io/ -> repo root (tensorrent_tent_io_publish)
    return Path(__file__).resolve().parents[3]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def internal_harness_snapshot(root: Path) -> dict[str, Any]:
    expansion = root / "tent_io" / "harness" / "reports" / "expansion" / "llt_expansion_sweep.current.json"
    intel = root / "tent_io" / "harness" / "reports" / "expansion" / "intelligence_scoring.current.json"
    out: dict[str, Any] = {
        "expansion_sweep_path": str(expansion),
        "intelligence_scoring_path": str(intel),
        "best_profile": None,
        "rank_by": None,
        "metrics": {},
        "intelligence_scores": {},
    }
    sweep = load_json(expansion)
    if sweep:
        out["rank_by"] = sweep.get("rank_by")
        best = sweep.get("best_profile") if isinstance(sweep.get("best_profile"), dict) else {}
        out["best_profile"] = best.get("profile")
        out["metrics"] = {
            "final_test_acc": best.get("final_test_acc"),
            "final_mmlu_test_acc": best.get("final_mmlu_test_acc"),
            "final_conversational_logic_test_acc": best.get("final_conversational_logic_test_acc"),
            "train_eval_drift": best.get("train_eval_drift"),
            "replay_test_acc": best.get("replay_test_acc"),
        }
    scoring = load_json(intel)
    if scoring:
        scores = scoring.get("scores") if isinstance(scoring.get("scores"), dict) else {}
        out["intelligence_scores"] = {
            k: scores.get(k)
            for k in (
                "ml_intelligence_score",
                "logic_chain_score",
                "ai_intelligence_score",
                "agi_readiness_score",
            )
        }
        out["scoring_preset"] = scoring.get("scoring_preset")
        out["scoring_version"] = scoring.get("scoring_version")
    return out


def inference_mode_antigravity() -> str:
    if os.environ.get("ANTIGRAVITY_INFERENCE_URL", "").strip():
        return "http"
    if cli_binary_configured():
        return "cli"
    return "stub"


def run_odin(root: Path, out_ndjson: Path) -> dict[str, Any]:
    script = root / "tent_io" / "harness" / "odin_real_benchmark.py"
    env = os.environ.copy()
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--out",
            str(out_ndjson),
            "--no-spec-sheet",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=120,
    )
    # stderr: "ODIN real benchmark: passed/total ..."
    m = re.search(r"ODIN real benchmark:\s*(\d+)/(\d+)", proc.stderr or "")
    passed, total = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    acc = (passed / total) if passed is not None and total else None
    return {
        "lane": "odin_mmlu_pro_sample",
        "script": str(script),
        "questions_default": str(root / "tent_io" / "harness" / "fixtures" / "mmlu_pro_sample.json"),
        "inference_mode": inference_mode_antigravity(),
        "returncode": proc.returncode,
        "passed": passed,
        "total": total,
        "accuracy_0_1": acc,
        "note": "Stub inference returns empty answers unless ANTIGRAVITY_INFERENCE_URL is set or a CLI binary is resolved (HARNESS_CLI_BIN / INFERENCE_BIN / ANTIGRAVITY_BIN / TENT_INFERENCE_BIN).",
        "ndjson_out": str(out_ndjson),
    }


def run_gsm8k_heuristic(root: Path) -> dict[str, Any]:
    test_path = root / "tent_io" / "harness" / "fixtures" / "training" / "gsm8k_test.jsonl"
    script = root / "tent_io" / "harness" / "training" / "eval_gsm8k_solver.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--gsm8k-test-jsonl", str(test_path)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=120,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception:
        payload = {"parse_error": True, "stdout": proc.stdout[:500]}
    payload["lane"] = "gsm8k_heuristic_baseline"
    payload["script"] = str(script)
    payload["returncode"] = proc.returncode
    payload["note"] = "Heuristic solver baseline from eval_gsm8k_solver.py; not the LLT model unless wired."
    return payload


def run_tent_v41_lane(root: Path, reports_dir: Path, use_cli_env: bool) -> dict[str, Any]:
    bundle = root / "tent_io" / "harness" / "tent_v41_external_benchmark"
    script = bundle / "tent_benchmark_adapter.py"
    questions = bundle / "benchmark_questions_10_builtin.json"
    out_logs = reports_dir / "intel_snapshot_tent_v41_atomic.json"
    out_summary = reports_dir / "intel_snapshot_tent_v41_summary.json"
    out_tx = reports_dir / "intel_snapshot_tent_v41_transcript.txt"
    env = os.environ.copy()
    if not use_cli_env:
        env["TENT_INFERENCE_PATTERN"] = "stub"
    pattern = (env.get("TENT_INFERENCE_PATTERN") or "").strip().lower()
    bin_ok = resolve_cli_binary_from_env(env) is not None
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--questions",
            str(questions),
            "--out-logs",
            str(out_logs),
            "--out-summary",
            str(out_summary),
            "--out-transcript",
            str(out_tx),
        ],
        cwd=str(bundle),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    summary = load_json(out_summary)
    if use_cli_env:
        lane = "tent_v41_external_builtin_cli"
        if pattern == "http":
            mode = "http"
        elif pattern == "cli":
            mode = "cli" if bin_ok else "cli_bin_missing"
        elif pattern == "stub":
            mode = "stub"
        else:
            mode = pattern or "env_unset"
    else:
        lane = "tent_v41_external_builtin_stub"
        mode = "stub"
    return {
        "lane": lane,
        "inference_mode": mode,
        "tent_inference_pattern": pattern or ("stub" if not use_cli_env else ""),
        "tent_inference_bin_configured": bin_ok,
        "returncode": proc.returncode,
        "summary_path": str(out_summary),
        "summary": summary,
        "stderr_tail": (proc.stderr or "")[-400:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Intel benchmark snapshot (internal + local lanes)")
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Default: tent_io/harness/reports/intel_benchmark_snapshot.current.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=None,
        help="Default: tent_io/harness/reports/intel_benchmark_snapshot.current.md",
    )
    parser.add_argument("--skip-odin", action="store_true")
    parser.add_argument("--skip-gsm8k", action="store_true")
    parser.add_argument("--skip-tent-v41", action="store_true")
    parser.add_argument(
        "--tent-v41-cli",
        action="store_true",
        help="Do not force TENT_INFERENCE_PATTERN=stub; use shell env (e.g. TENT_INFERENCE_PATTERN=cli plus HARNESS_CLI_BIN or legacy *_BIN vars).",
    )
    args = parser.parse_args()

    root = repo_root()
    reports_dir = root / "tent_io" / "harness" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_json or (reports_dir / "intel_benchmark_snapshot.current.json")
    out_md = args.out_md or (reports_dir / "intel_benchmark_snapshot.current.md")

    snapshot: dict[str, Any] = {
        "status": "ok",
        "snapshot_kind": "intel_benchmark_status",
        "repo_root": str(root),
        "internal_harness": internal_harness_snapshot(root),
        "lanes": {},
    }

    if not args.skip_odin:
        odin_out = reports_dir / "intel_snapshot_odin.ndjson"
        snapshot["lanes"]["odin"] = run_odin(root, odin_out)
    if not args.skip_gsm8k:
        snapshot["lanes"]["gsm8k_heuristic"] = run_gsm8k_heuristic(root)
    if not args.skip_tent_v41:
        snapshot["lanes"]["tent_v41"] = run_tent_v41_lane(root, reports_dir, use_cli_env=args.tent_v41_cli)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    lines = [
        "# Intelligence benchmark snapshot",
        "",
        "## Internal harness (from artifacts if present)",
        "",
        f"- best_profile: `{snapshot['internal_harness'].get('best_profile')}`",
        f"- rank_by: `{snapshot['internal_harness'].get('rank_by')}`",
        f"- metrics: `{snapshot['internal_harness'].get('metrics')}`",
        f"- intelligence_scores: `{snapshot['internal_harness'].get('intelligence_scores')}`",
        "",
        "## Lanes",
        "",
    ]
    for name, payload in snapshot["lanes"].items():
        lines.append(f"### {name}")
        lines.append(f"- `{json.dumps(payload, ensure_ascii=True)[:800]}`")
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "",
            "- Internal metrics are from the in-repo LLT expansion pipeline (as reported).",
            "- ODIN / TENT v4.1 stub lanes validate wiring; accuracy is not a frontier comparison unless a real inference backend is configured.",
            "- GSM8K row reports a heuristic baseline unless a model-backed solver is integrated.",
            "",
            f"Full JSON: `{out_json}`",
        ]
    )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out_json": str(out_json), "out_md": str(out_md)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
