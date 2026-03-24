#!/usr/bin/env python3
"""
TENT v4.1 External Benchmark — Adapter (Phase C).

Reads benchmark_questions_100.json (or GPQA variant), runs each question through TENT,
logs per-question atomic JSON, writes summary and human-readable transcript.

Inference pattern (set TENT_INFERENCE_PATTERN and corresponding env):
  stub   — no engine (for pipeline test). No env.
  cli    — shared harness: set HARNESS_CLI_BIN or INFERENCE_BIN or ANTIGRAVITY_BIN or TENT_INFERENCE_BIN (subprocess: --prompt and --question-id; see tent_io/harness/cli_inference_harness.py)
  http   — TENT_INFERENCE_URL=http://localhost:PORT/infer (POST json {"prompt": "..."})
  wasm   — [future] wasmtime/wasmer
  python — [future] from tent_core import infer
  file   — [future] write input.json, read output.json (Antigravity IDE)

Non-negotiable per-question fields: prompt_sent_to_tent, tent_raw_output, expected_answer, is_correct.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_HARNESS_DIR = Path(__file__).resolve().parent.parent
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))
from cli_inference_harness import (  # noqa: E402
    cli_binary_resolution_hint,
    resolve_cli_binary,
    run_cli_inference,
)

BUNDLE_DIR = Path(__file__).resolve().parent
DEFAULT_QUESTIONS = BUNDLE_DIR / "benchmark_questions_100.json"
BUILTIN_QUESTIONS = BUNDLE_DIR / "benchmark_questions_10_builtin.json"
DEFAULT_LOGS = BUNDLE_DIR / "tent_eval_atomic_logs.json"
DEFAULT_SUMMARY = BUNDLE_DIR / "tent_eval_summary.json"
DEFAULT_TRANSCRIPT = BUNDLE_DIR / "tent_eval_transcript.txt"


def load_questions(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("questions", [])


def build_prompt(q: dict) -> str:
    lines = [q.get("question", "")]
    for opt in q.get("options", []):
        lines.append(opt)
    lines.append("\nAnswer with the letter only (A, B, C, or D).")
    return "\n".join(lines)


def extract_answer(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip().upper()
    m = re.search(r"\b([A-D])\b", s)
    return m.group(1) if m else (s[:1] if s else "")


def grade(expected: str, extracted: str) -> tuple[bool, str, str]:
    exp = (expected or "").strip().upper()[:1]
    got = (extracted or "").strip().upper()[:1]
    correct = got == exp
    method = "exact_match_letter"
    detail = f"extracted={repr(got)} == expected={repr(exp)}"
    return correct, method, detail


# --- Inference backends ---

def infer_stub(prompt: str, question_id: str) -> str:
    return ""


def infer_http(prompt: str, question_id: str, url: str) -> str:
    req = urllib.request.Request(
        url,
        data=json.dumps({"prompt": prompt, "question_id": question_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read().decode())
    return out.get("output") or out.get("text") or out.get("response") or str(out)


def call_tent(prompt: str, question_id: str) -> str:
    pattern = (os.environ.get("TENT_INFERENCE_PATTERN") or "stub").strip().lower()
    if pattern == "cli":
        if resolve_cli_binary():
            return run_cli_inference(prompt, question_id, cwd=BUNDLE_DIR, timeout=120)
        return f"[ERROR no CLI binary resolved; set one of {cli_binary_resolution_hint()}]"
    if pattern == "http":
        url = os.environ.get("TENT_INFERENCE_URL", "").strip()
        if url:
            return infer_http(prompt, question_id, url)
        return "[ERROR TENT_INFERENCE_URL not set]"
    return infer_stub(prompt, question_id)


def run_eval(
    questions_path: Path,
    out_logs: Path,
    out_summary: Path,
    out_transcript: Path,
    core_footprint_bytes: int | None = None,
    network_note: str = "",
) -> int:
    questions = load_questions(questions_path)
    if not questions:
        print("No questions found.", file=sys.stderr)
        return 1

    logs = []
    total_ms = 0.0
    start_wall = time.perf_counter()
    category_stats: dict[str, dict] = {}

    for i, q in enumerate(questions):
        qid = q.get("id", f"q{i}")
        category = q.get("category", "unknown")
        expected = q.get("expected_answer", "A")
        prompt = build_prompt(q)

        t0 = time.perf_counter()
        raw_output = call_tent(prompt, qid)
        elapsed_ns = int((time.perf_counter() - t0) * 1e9)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        total_ms += elapsed_ms

        extracted = extract_answer(raw_output)
        correct, grading_method, grading_detail = grade(expected, extracted)

        if category not in category_stats:
            category_stats[category] = {"total": 0, "correct": 0}
        category_stats[category]["total"] += 1
        if correct:
            category_stats[category]["correct"] += 1

        atom = {
            "question_index": i + 1,
            "question_id": qid,
            "category": category,
            "question_text": q.get("question", ""),
            "options": q.get("options", []),
            "expected_answer": expected,
            "prompt_sent_to_tent": prompt,
            "tent_raw_output": raw_output,
            "tent_extracted_answer": extracted,
            "is_correct": correct,
            "grading_method": grading_method,
            "grading_detail": grading_detail,
            "inference_time_ns": elapsed_ns,
            "inference_time_ms": round(elapsed_ms, 6),
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        }
        logs.append(atom)

    total_wall = time.perf_counter() - start_wall
    correct_count = sum(1 for a in logs if a["is_correct"])
    total_count = len(logs)
    accuracy = (100.0 * correct_count / total_count) if total_count else 0.0
    avg_ms = total_ms / total_count if total_count else 0

    category_breakdown = {}
    for cat, st in category_stats.items():
        t, c = st["total"], st["correct"]
        category_breakdown[cat] = {"total": t, "correct": c, "accuracy": round(100.0 * c / t, 1) if t else 0}

    # Write atomic logs
    out_logs.parent.mkdir(parents=True, exist_ok=True)
    with open(out_logs, "w") as f:
        json.dump(logs, f, indent=2)

    source_name = questions[0].get("source", "unknown") if questions else "unknown"
    benchmark_name = "MMLU-Pro" if "mmlu" in source_name.lower() or "mmlu" in str(questions_path).lower() else "GPQA Diamond" if "gpqa" in source_name.lower() or "gpqa" in str(questions_path).lower() else "TENT v4.1 validation (built-in)"
    summary = {
        "benchmark": benchmark_name,
        "source": source_name,
        "model": "TENT v4.1",
        "total_questions": total_count,
        "correct": correct_count,
        "incorrect": total_count - correct_count,
        "accuracy_percent": round(accuracy, 2),
        "average_inference_ms": round(avg_ms, 4),
        "total_runtime_seconds": round(total_wall, 2),
        "core_footprint_bytes": core_footprint_bytes,
        "network_isolation": network_note or "(not captured)",
        "category_breakdown": category_breakdown,
    }
    with open(out_summary, "w") as f:
        json.dump(summary, f, indent=2)

    with open(out_transcript, "w") as f:
        f.write("TENT v4.1 External Benchmark — Transcript\n")
        f.write("=" * 60 + "\n\n")
        for a in logs:
            f.write(f"--- {a['question_id']} (correct={a['is_correct']}) ---\n")
            f.write(f"Q: {a['question_text'][:200]}...\n" if len(a['question_text']) > 200 else f"Q: {a['question_text']}\n")
            f.write(f"Expected: {a['expected_answer']}\n")
            f.write(f"TENT raw: {a['tent_raw_output'][:300]}...\n" if len(a['tent_raw_output']) > 300 else f"TENT raw: {a['tent_raw_output']}\n")
            f.write(f"Extracted: {a['tent_extracted_answer']}\n\n")
    print(f"Correct: {correct_count}/{total_count} ({accuracy:.1f}%)", file=sys.stderr)
    print(f"Logs: {out_logs}", file=sys.stderr)
    print(f"Summary: {out_summary}", file=sys.stderr)
    print(f"Transcript: {out_transcript}", file=sys.stderr)
    return 0 if correct_count == total_count else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="TENT v4.1 benchmark adapter — run inference, log atomic JSON")
    ap.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS, help="Path to benchmark_questions_100.json")
    ap.add_argument("--out-logs", type=Path, default=DEFAULT_LOGS, help="Output atomic logs JSON")
    ap.add_argument("--out-summary", type=Path, default=DEFAULT_SUMMARY, help="Output summary JSON")
    ap.add_argument("--out-transcript", type=Path, default=DEFAULT_TRANSCRIPT, help="Output transcript txt")
    ap.add_argument("--core-footprint", type=int, default=None, help="Core binary size in bytes (for summary)")
    ap.add_argument("--network-note", type=str, default="", help="e.g. 'confirmed (tcpdump: 0 outbound)'")
    args = ap.parse_args()
    if not args.questions.exists():
        if DEFAULT_QUESTIONS == args.questions and BUILTIN_QUESTIONS.exists():
            args.questions = BUILTIN_QUESTIONS
            print(f"Using built-in questions: {args.questions}", file=sys.stderr)
        else:
            print(f"Questions file not found: {args.questions}", file=sys.stderr)
            print("Run fetch_mmlu_pro_100.py or fetch_gpqa_100.py, or use --questions benchmark_questions_10_builtin.json", file=sys.stderr)
            return 1
    return run_eval(
        args.questions,
        args.out_logs,
        args.out_summary,
        args.out_transcript,
        core_footprint_bytes=args.core_footprint,
        network_note=args.network_note or os.environ.get("TENT_NETWORK_NOTE", ""),
    )


if __name__ == "__main__":
    sys.exit(main())
