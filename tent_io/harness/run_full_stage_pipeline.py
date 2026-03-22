#!/usr/bin/env python3
"""Run all integration stages in one auditable command."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def parse_last_json_object(text: str) -> dict[str, object]:
    decoder = json.JSONDecoder()
    i = 0
    last: dict[str, object] = {}
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, i)
            if isinstance(obj, dict):
                last = obj
            i = max(end, i + 1)
        except Exception:
            i += 1
    return last


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SparsePlug/Bingo/SEGGCI/OmniForge stage pipeline")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Production alias: enables strict fail-closed execution with default voxel quality gate.",
    )
    parser.add_argument("--strict", action="store_true", help="Fail closed on stage error")
    parser.add_argument("--with-bingo", action="store_true", help="Include Bingo stage in orchestrator")
    parser.add_argument(
        "--with-voxel-eval",
        action="store_true",
        help="Run voxel-stack best-checkpoint eval as post stage",
    )
    parser.add_argument(
        "--with-llt-train",
        action="store_true",
        help="Run liquid language model training as post stage.",
    )
    parser.add_argument(
        "--with-llt-eval",
        action="store_true",
        help="Run liquid language model best-checkpoint eval as post stage.",
    )
    parser.add_argument(
        "--skip-voxel-eval",
        action="store_true",
        help="Disable voxel post-stage (even in strict mode).",
    )
    parser.add_argument(
        "--skip-llt-train",
        action="store_true",
        help="Disable LLT training post-stage (even in strict/production mode).",
    )
    parser.add_argument(
        "--skip-llt-eval",
        action="store_true",
        help="Disable LLT eval post-stage (even in strict/production mode).",
    )
    parser.add_argument("--voxel-best-link", default="best_voxel_hybrid_step")
    parser.add_argument("--voxel-samples-per-step", type=int, default=40)
    parser.add_argument("--voxel-seed", type=int, default=19)
    parser.add_argument("--voxel-min-hybrid-step-acc", type=float, default=0.60)
    parser.add_argument("--voxel-min-stack-acc", type=float, default=0.65)
    parser.add_argument("--llt-epochs", type=int, default=1)
    parser.add_argument("--llt-hidden-dim", type=int, default=48)
    parser.add_argument("--llt-max-train", type=int, default=512)
    parser.add_argument("--llt-max-test", type=int, default=256)
    parser.add_argument("--llt-min-test-acc", type=float, default=0.20)
    parser.add_argument("--llt-min-mmlu-test-acc", type=float, default=-1.0)
    parser.add_argument("--llt-min-conversational-test-acc", type=float, default=-1.0)
    parser.add_argument("--llt-min-eval-acc", type=float, default=0.20)
    parser.add_argument("--llt-min-eval-mmlu-acc", type=float, default=-1.0)
    parser.add_argument("--llt-min-eval-conversational-acc", type=float, default=-1.0)
    parser.add_argument("--llt-max-replay-drift", type=float, default=1e-12)
    parser.add_argument("--disable-conversational-logic", action="store_true")
    parser.add_argument("--conversation-train-rows", type=int, default=256)
    parser.add_argument("--conversation-test-rows", type=int, default=128)
    parser.add_argument("--conversation-seed", type=int, default=17)
    parser.add_argument("--skip-upg-export", action="store_true", help="Skip UPG training/teaching export stage.")
    parser.add_argument("--skip-midi-scroll-export", action="store_true", help="Skip UPG->MIDI persistent scroll export.")
    parser.add_argument("--skip-merkle-scroll-export", action="store_true", help="Skip Merkle bit-hash tensor-scroll export.")
    parser.add_argument("--no-merkle-cache-reuse", action="store_true", help="Disable Merkle map cache reuse.")
    parser.add_argument("--midi-max-points", type=int, default=256)
    parser.add_argument("--query", default="system profile check")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "tent_io" / "harness" / "reports" / "full_stage_pipeline.current.json",
    )
    args = parser.parse_args()
    strict_mode = args.strict or args.production
    run_voxel_eval = (args.with_voxel_eval or strict_mode) and not args.skip_voxel_eval
    run_llt_train = (args.with_llt_train or strict_mode) and not args.skip_llt_train
    run_llt_eval = (args.with_llt_eval or strict_mode) and not args.skip_llt_eval
    run_upg_export = not args.skip_upg_export
    run_midi_scroll_export = run_upg_export and not args.skip_midi_scroll_export
    run_merkle_scroll_export = run_midi_scroll_export and not args.skip_merkle_scroll_export


    root = REPO_ROOT
    run_started = datetime.now(timezone.utc)
    run_id = run_started.strftime("%Y%m%dT%H%M%S") + f"{run_started.microsecond // 1000:03d}Z"
    report: dict[str, object] = {
        "run_id": run_id,
        "timestamp_utc": run_started.isoformat().replace("+00:00", "Z"),
        "production": args.production,
        "strict": strict_mode,
        "with_bingo": args.with_bingo,
        "with_voxel_eval": run_voxel_eval,
        "with_llt_train": run_llt_train,
        "with_llt_eval": run_llt_eval,
        "with_upg_export": run_upg_export,
        "with_midi_scroll_export": run_midi_scroll_export,
        "with_merkle_scroll_export": run_merkle_scroll_export,
        "llt_drift_summary": {
            "train_and_replay_compared": False,
            "train_final_test_acc": None,
            "replay_test_acc": None,
            "train_eval_drift": None,
            "max_replay_drift": args.llt_max_replay_drift,
            "drift_passes": None,
        },
        "stages": {},
    }

    stages = [
        (
            "generate_sparseplug_decision",
            ["python3", "tent_io/harness/generate_sparseplug_decision.py"],
        ),
        (
            "validate_sparseplug_decision",
            [
                "python3",
                "tent_io/harness/validate_sparseplug_decision.py",
                "--decision-json",
                "tent_io/harness/reports/sparseplug_decision.current.json",
                "--strict-hash",
            ],
        ),
    ]

    orch_cmd = [
        "python3",
        "tent_io/harness/run_seggci_omniforge_stack.py",
        "--query",
        args.query,
    ]
    if strict_mode:
        orch_cmd.append("--strict")
    if args.with_bingo:
        orch_cmd.append("--with-bingo")
    stages.append(("run_stack_orchestrator", orch_cmd))

    if run_voxel_eval:
        stages.append(
            (
                "eval_voxel_stack_best",
                [
                    "python3",
                    "tent_io/harness/training/eval_voxel_stack_best.py",
                    "--best-link",
                    args.voxel_best_link,
                    "--samples-per-step",
                    str(args.voxel_samples_per_step),
                    "--seed",
                    str(args.voxel_seed),
                ],
            )
        )
    if run_llt_train:
        stages.append(
            (
                "train_liquid_language_model",
                [
                    "python3",
                    "tent_io/harness/training/train_liquid_language_model.py",
                    "--epochs",
                    str(args.llt_epochs),
                    "--hidden-dim",
                    str(args.llt_hidden_dim),
                    "--max-train",
                    str(args.llt_max_train),
                    "--max-test",
                    str(args.llt_max_test),
                    "--conversation-train-rows",
                    str(args.conversation_train_rows),
                    "--conversation-test-rows",
                    str(args.conversation_test_rows),
                    "--conversation-seed",
                    str(args.conversation_seed),
                ],
            )
        )
        if args.disable_conversational_logic:
            stages[-1][1].append("--disable-conversational-logic")
    if run_llt_eval:
        stages.append(
            (
                "eval_liquid_language_model_best",
                [
                    "python3",
                    "tent_io/harness/training/eval_liquid_language_model_best.py",
                    "--best-link",
                    "best_liquid_llt",
                    "--max-test",
                    str(args.llt_max_test),
                    "--conversation-test-rows",
                    str(args.conversation_test_rows),
                    "--conversation-seed",
                    str(args.conversation_seed),
                ],
            )
        )
        if args.disable_conversational_logic:
            stages[-1][1].append("--disable-conversational-logic")
        stages.append(
            (
                "compare_liquid_runs",
                [
                    "python3",
                    "tent_io/harness/training/compare_liquid_runs.py",
                    "--update-best-links",
                    "--write-summary-json",
                ],
            )
        )

    overall_rc = 0
    llt_train_acc_for_replay: float | None = None
    llt_eval_acc_for_replay: float | None = None
    for name, cmd in stages:
        cmd_to_run = list(cmd)
        if name == "eval_liquid_language_model_best" and run_llt_train:
            train_stage = report["stages"].get("train_liquid_language_model")
            if isinstance(train_stage, dict):
                train_stdout = train_stage.get("stdout")
                if isinstance(train_stdout, str):
                    try:
                        payload = parse_last_json_object(train_stdout)
                        artifacts_dir = payload.get("artifacts_dir")
                        if isinstance(artifacts_dir, str) and artifacts_dir:
                            cmd_to_run.extend(["--checkpoint-dir", artifacts_dir])
                    except Exception:
                        pass
        rc, out, err = run_cmd(cmd_to_run, cwd=root)
        report["stages"][name] = {"rc": rc, "stdout": out.strip(), "stderr": err.strip(), "cmd": cmd_to_run}
        if rc != 0 and overall_rc == 0:
            overall_rc = rc
            if strict_mode:
                break

        # In strict production mode, gate on voxel quality thresholds.
        if strict_mode and name == "eval_voxel_stack_best" and rc == 0:
            try:
                payload = json.loads(out)
                hybrid = float(payload.get("hybrid_step_acc", 0.0))
                stack = float(payload.get("stack_acc", 0.0))
            except Exception:
                hybrid = 0.0
                stack = 0.0
            gates = {
                "hybrid_step_acc": hybrid,
                "stack_acc": stack,
                "min_hybrid_step_acc": args.voxel_min_hybrid_step_acc,
                "min_stack_acc": args.voxel_min_stack_acc,
                "passes": hybrid >= args.voxel_min_hybrid_step_acc and stack >= args.voxel_min_stack_acc,
            }
            report["stages"][name]["gates"] = gates  # type: ignore[index]
            if not gates["passes"] and overall_rc == 0:
                overall_rc = 3
                break
        if strict_mode and name == "train_liquid_language_model" and rc == 0:
            llt_acc = 0.0
            llt_mmlu_acc = 0.0
            llt_conv_acc = 0.0
            try:
                payload = parse_last_json_object(out)
                llt_acc = float(payload.get("final_test_acc", 0.0))
                llt_mmlu_acc = float(payload.get("final_mmlu_test_acc", 0.0))
                llt_conv_acc = float(payload.get("final_conversational_logic_test_acc", 0.0))
            except Exception:
                pass
            llt_train_acc_for_replay = llt_acc
            split_mmlu_enabled = args.llt_min_mmlu_test_acc >= 0.0
            split_conv_enabled = args.llt_min_conversational_test_acc >= 0.0
            split_mmlu_passes = (not split_mmlu_enabled) or (llt_mmlu_acc >= args.llt_min_mmlu_test_acc)
            split_conv_passes = (not split_conv_enabled) or (
                llt_conv_acc >= args.llt_min_conversational_test_acc
            )
            gates = {
                "final_test_acc": llt_acc,
                "final_mmlu_test_acc": llt_mmlu_acc,
                "final_conversational_logic_test_acc": llt_conv_acc,
                "min_test_acc": args.llt_min_test_acc,
                "min_mmlu_test_acc": args.llt_min_mmlu_test_acc,
                "min_conversational_test_acc": args.llt_min_conversational_test_acc,
                "mmlu_split_gate_enabled": split_mmlu_enabled,
                "conversational_split_gate_enabled": split_conv_enabled,
                "mmlu_split_passes": split_mmlu_passes,
                "conversational_split_passes": split_conv_passes,
                "passes": (llt_acc >= args.llt_min_test_acc) and split_mmlu_passes and split_conv_passes,
            }
            report["stages"][name]["gates"] = gates  # type: ignore[index]
            if not gates["passes"] and overall_rc == 0:
                overall_rc = 4
                break
        if strict_mode and name == "eval_liquid_language_model_best" and rc == 0:
            llt_eval_acc = 0.0
            llt_eval_mmlu_acc = 0.0
            llt_eval_conv_acc = 0.0
            try:
                payload = parse_last_json_object(out)
                llt_eval_acc = float(payload.get("test_acc", 0.0))
                llt_eval_mmlu_acc = float(payload.get("mmlu_test_acc", 0.0))
                llt_eval_conv_acc = float(payload.get("conversational_logic_test_acc", 0.0))
            except Exception:
                pass
            llt_eval_acc_for_replay = llt_eval_acc
            split_mmlu_enabled = args.llt_min_eval_mmlu_acc >= 0.0
            split_conv_enabled = args.llt_min_eval_conversational_acc >= 0.0
            split_mmlu_passes = (not split_mmlu_enabled) or (llt_eval_mmlu_acc >= args.llt_min_eval_mmlu_acc)
            split_conv_passes = (not split_conv_enabled) or (
                llt_eval_conv_acc >= args.llt_min_eval_conversational_acc
            )
            gates = {
                "test_acc": llt_eval_acc,
                "mmlu_test_acc": llt_eval_mmlu_acc,
                "conversational_logic_test_acc": llt_eval_conv_acc,
                "min_eval_acc": args.llt_min_eval_acc,
                "min_eval_mmlu_acc": args.llt_min_eval_mmlu_acc,
                "min_eval_conversational_acc": args.llt_min_eval_conversational_acc,
                "mmlu_split_gate_enabled": split_mmlu_enabled,
                "conversational_split_gate_enabled": split_conv_enabled,
                "mmlu_split_passes": split_mmlu_passes,
                "conversational_split_passes": split_conv_passes,
                "passes": (llt_eval_acc >= args.llt_min_eval_acc) and split_mmlu_passes and split_conv_passes,
            }
            if run_llt_train and llt_train_acc_for_replay is not None:
                replay_drift = abs(llt_eval_acc - llt_train_acc_for_replay)
                gates["train_eval_drift"] = replay_drift
                gates["max_replay_drift"] = args.llt_max_replay_drift
                gates["drift_passes"] = replay_drift <= args.llt_max_replay_drift
                gates["passes"] = bool(gates["passes"]) and bool(gates["drift_passes"])
            report["stages"][name]["gates"] = gates  # type: ignore[index]
            if not gates["passes"] and overall_rc == 0:
                overall_rc = 5
                break

    drift_summary = report.get("llt_drift_summary")
    if isinstance(drift_summary, dict):
        drift_summary["train_final_test_acc"] = llt_train_acc_for_replay
        drift_summary["replay_test_acc"] = llt_eval_acc_for_replay
        if run_llt_train and run_llt_eval and llt_train_acc_for_replay is not None and llt_eval_acc_for_replay is not None:
            replay_drift = abs(llt_eval_acc_for_replay - llt_train_acc_for_replay)
            drift_summary["train_and_replay_compared"] = True
            drift_summary["train_eval_drift"] = replay_drift
            drift_summary["drift_passes"] = replay_drift <= args.llt_max_replay_drift

    report["status"] = "ok" if overall_rc == 0 else "partial_or_failed"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=True)

    if run_upg_export:
        upg_cmd = [
            "python3",
            "tent_io/harness/export_upg_training_record.py",
            "--pipeline-report",
            str(args.out),
        ]
        rc, out, err = run_cmd(upg_cmd, cwd=root)
        report["stages"]["export_upg_training_record"] = {
            "rc": rc,
            "stdout": out.strip(),
            "stderr": err.strip(),
            "cmd": upg_cmd,
        }
        if rc != 0 and overall_rc == 0:
            overall_rc = rc

        report["status"] = "ok" if overall_rc == 0 else "partial_or_failed"
        with args.out.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=True)

    if run_midi_scroll_export:
        upg_record_path = "/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_training_record.current.json"
        upg_stage = report["stages"].get("export_upg_training_record")
        if isinstance(upg_stage, dict):
            upg_stdout = upg_stage.get("stdout")
            if isinstance(upg_stdout, str):
                try:
                    upg_payload = json.loads(upg_stdout)
                    out_path = upg_payload.get("out")
                    if isinstance(out_path, str) and out_path:
                        upg_record_path = out_path
                except Exception:
                    pass

        midi_cmd = [
            "python3",
            "tent_io/harness/export_upg_midi_scroll.py",
            "--upg-record",
            upg_record_path,
            "--max-points",
            str(args.midi_max_points),
        ]
        rc, out, err = run_cmd(midi_cmd, cwd=root)
        report["stages"]["export_upg_midi_scroll"] = {
            "rc": rc,
            "stdout": out.strip(),
            "stderr": err.strip(),
            "cmd": midi_cmd,
        }
        if rc != 0 and overall_rc == 0:
            overall_rc = rc

        report["status"] = "ok" if overall_rc == 0 else "partial_or_failed"
        with args.out.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=True)

    if run_merkle_scroll_export:
        scroll_path = "/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_prime_pins_scroll.current.ndjson"
        midi_stage = report["stages"].get("export_upg_midi_scroll")
        if isinstance(midi_stage, dict):
            midi_stdout = midi_stage.get("stdout")
            if isinstance(midi_stdout, str):
                try:
                    midi_payload = json.loads(midi_stdout)
                    out_scroll = midi_payload.get("out_scroll")
                    if isinstance(out_scroll, str) and out_scroll:
                        scroll_path = out_scroll
                except Exception:
                    pass

        merkle_cmd = [
            "python3",
            "tent_io/harness/export_merkle_tensor_scroll.py",
            "--scroll",
            scroll_path,
        ]
        if not args.no_merkle_cache_reuse:
            merkle_cmd.append("--reuse-cache")
        rc, out, err = run_cmd(merkle_cmd, cwd=root)
        report["stages"]["export_merkle_tensor_scroll"] = {
            "rc": rc,
            "stdout": out.strip(),
            "stderr": err.strip(),
            "cmd": merkle_cmd,
        }
        if rc != 0 and overall_rc == 0:
            overall_rc = rc

        report["status"] = "ok" if overall_rc == 0 else "partial_or_failed"
        with args.out.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=True)

    print(json.dumps({"out": str(args.out), "status": report["status"]}, indent=2))
    if strict_mode and overall_rc != 0:
        return overall_rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
