#!/usr/bin/env python3
"""Deterministic external-eval lane scaffold for LLT profile comparisons.

This stage is intentionally non-blocking and currently computes proxy metrics from
profile pipeline artifacts plus the local benchmark summary snapshot when present.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing JSON: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected object JSON: {path}")
    return payload


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute deterministic external-eval proxy metrics per profile.")
    parser.add_argument("--profile", required=True, help="Profile label (example: expand_s2).")
    parser.add_argument("--pipeline-report", type=Path, required=True, help="full_stage_pipeline.<profile>.*.json path.")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path.")
    parser.add_argument(
        "--benchmark-summary",
        type=Path,
        default=Path("tent_io/harness/tent_v41_external_benchmark/tent_eval_summary.json"),
        help="Optional benchmark summary JSON used as an additive context signal.",
    )
    args = parser.parse_args()

    report = load_json(args.pipeline_report)
    train = report.get("stages", {}).get("train_liquid_language_model", {})
    train_gates = train.get("gates", {}) if isinstance(train.get("gates"), dict) else {}
    replay = report.get("stages", {}).get("eval_liquid_language_model_best", {})
    replay_gates = replay.get("gates", {}) if isinstance(replay.get("gates"), dict) else {}
    drift = report.get("llt_drift_summary", {}) if isinstance(report.get("llt_drift_summary"), dict) else {}

    train_mmlu = as_float(train_gates.get("final_mmlu_test_acc"))
    train_conv = as_float(train_gates.get("final_conversational_logic_test_acc"))
    train_final = as_float(train_gates.get("final_test_acc"))
    replay_mmlu = as_float(replay_gates.get("mmlu_test_acc"))
    replay_conv = as_float(replay_gates.get("conversational_logic_test_acc"))
    replay_final = as_float(replay_gates.get("test_acc"))
    train_eval_drift = as_float(drift.get("train_eval_drift"))

    bench_acc = None
    benchmark_path_used = None
    benchmark_name = None
    if args.benchmark_summary.exists():
        bench = load_json(args.benchmark_summary)
        benchmark_path_used = str(args.benchmark_summary)
        benchmark_name = bench.get("benchmark") if isinstance(bench.get("benchmark"), str) else None
        raw_acc = as_float(bench.get("accuracy_percent"))
        if raw_acc is not None:
            bench_acc = clamp01(raw_acc / 100.0)

    # Proxy-only deterministic lane:
    # - MMLU/conv combine train+replay profile scores with optional benchmark context.
    # - Long-context proxy uses stable average of final test train/replay.
    # - Consistency penalizes non-zero drift and split divergence.
    mmlu_base = as_float(((train_mmlu or 0.0) + (replay_mmlu or (train_mmlu or 0.0))) / 2.0)
    conv_base = as_float(((train_conv or 0.0) + (replay_conv or (train_conv or 0.0))) / 2.0)
    long_base = as_float(((train_final or 0.0) + (replay_final or (train_final or 0.0))) / 2.0)
    drift_penalty = abs(train_eval_drift or 0.0)
    split_gap = abs((train_mmlu or 0.0) - (train_conv or 0.0))

    context = bench_acc if bench_acc is not None else 0.0
    mmlu_pro_proxy = clamp01(0.85 * (mmlu_base or 0.0) + 0.15 * context)
    gpqa_proxy = clamp01(0.85 * (conv_base or 0.0) + 0.15 * context)
    long_context_proxy = clamp01(0.90 * (long_base or 0.0) + 0.10 * context)
    consistency_score = clamp01(1.0 - min(1.0, drift_penalty * 1000000.0) - min(0.5, split_gap))

    out = {
        "status": "ok",
        "external_eval_mode": "proxy",
        "proxy_metrics": True,
        "profile": args.profile,
        "pipeline_report": str(args.pipeline_report),
        "benchmark_context": {
            "path": benchmark_path_used,
            "name": benchmark_name,
            "accuracy_0_1": bench_acc,
        },
        "metrics": {
            "mmlu_pro_acc": mmlu_pro_proxy,
            "gpqa_acc": gpqa_proxy,
            "long_context_acc": long_context_proxy,
            "consistency_score": consistency_score,
        },
        "inputs": {
            "train_mmlu_test_acc": train_mmlu,
            "replay_mmlu_test_acc": replay_mmlu,
            "train_conversational_test_acc": train_conv,
            "replay_conversational_test_acc": replay_conv,
            "train_final_test_acc": train_final,
            "replay_final_test_acc": replay_final,
            "train_eval_drift": train_eval_drift,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(args.out), "profile": args.profile}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
