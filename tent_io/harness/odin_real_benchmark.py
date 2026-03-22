#!/usr/bin/env python3
"""
ODIN real benchmark: pull MMLU-Pro questions → inference (Antigravity Rust/WASM) → grading + logging (tent-io harness) → atomic JSON.

Pipeline:
  Antigravity (Rust/WASM engine)  →  exposes inference
  tent-io harness                 →  wraps with grading + logging
  odin_real_benchmark.py          →  pulls MMLU-Pro questions, runs inference, grades, emits NDJSON + optional spec-sheet

Inference backend: ANTIGRAVITY_INFERENCE_URL (HTTP POST), ANTIGRAVITY_BIN (subprocess), or stub.
Atomic output: one JSON object per question (NDJSON) to file or stdout; optional summary + spec-sheet to harness/reports.
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
HARNESS_DIR = ROOT / "harness"
REPORTS_DIR = HARNESS_DIR / "reports"
FIXTURES_DIR = HARNESS_DIR / "fixtures"
DEFAULT_QUESTIONS_PATH = FIXTURES_DIR / "mmlu_pro_sample.json"


def load_questions(path: Path | None = None) -> list[dict[str, Any]]:
    """Load MMLU-Pro-style questions from JSON (list of {id, question, choices, answer_index, answer_key})."""
    path = path or Path(os.environ.get("ODIN_MMLU_PRO_QUESTIONS", str(DEFAULT_QUESTIONS_PATH)))
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("questions", [])


def call_inference_stub(prompt: str, question_id: str) -> str:
    """Stub when no Antigravity engine is configured. Returns placeholder."""
    # Stub: pick first choice as placeholder so grading can still run
    return ""


def call_inference_http(prompt: str, question_id: str, url: str) -> str:
    """POST prompt to inference URL; return response text. Expects JSON body with 'prompt', response with 'text' or 'response'."""
    req = urllib.request.Request(
        url,
        data=json.dumps({"prompt": prompt, "question_id": question_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read().decode())
    return out.get("text") or out.get("response") or str(out)


def call_inference_bin(prompt: str, question_id: str, bin_path: str) -> str:
    """Run Antigravity binary with prompt; read stdout as model answer."""
    import subprocess
    r = subprocess.run(
        [bin_path, "--prompt", prompt, "--question-id", question_id],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        return f"[ERROR exit {r.returncode}] {r.stderr or r.stdout or ''}"
    return (r.stdout or "").strip()


def call_inference(prompt: str, question_id: str) -> str:
    """Dispatch to HTTP, binary, or stub."""
    url = os.environ.get("ANTIGRAVITY_INFERENCE_URL", "").strip()
    if url:
        return call_inference_http(prompt, question_id, url)
    bin_path = os.environ.get("ANTIGRAVITY_BIN", "").strip()
    if bin_path and Path(bin_path).exists():
        return call_inference_bin(prompt, question_id, bin_path)
    return call_inference_stub(prompt, question_id)


def build_prompt(q: dict[str, Any]) -> str:
    """Build prompt for one question (question + choices)."""
    lines = [q.get("question", "")]
    choices = q.get("choices", [])
    keys = ["A", "B", "C", "D"][: len(choices)]
    for k, c in zip(keys, choices):
        lines.append(f"  {k}. {c}")
    lines.append("\nAnswer with the letter only (A, B, C, or D).")
    return "\n".join(lines)


def normalize_answer(s: str) -> str:
    """Normalize model output to a single choice letter."""
    if not s:
        return ""
    s = s.strip().upper()
    # Take first A/B/C/D
    m = re.search(r"\b([A-D])\b", s)
    return m.group(1) if m else s[:1] if s else ""


def grade_answer(q: dict[str, Any], model_answer: str) -> bool:
    """True if model answer matches expected (by key or by choice index)."""
    expected_key = (q.get("answer_key") or "ABCD"[q.get("answer_index", 0)]).strip().upper()
    got = normalize_answer(model_answer)
    if got == expected_key:
        return True
    # Allow match by choice text (first letter of correct choice)
    choices = q.get("choices", [])
    idx = q.get("answer_index", 0)
    if 0 <= idx < len(choices):
        expected_letter = "ABCD"[idx]
        return got == expected_letter
    return False


def run_benchmark(
    questions_path: Path | None = None,
    out_ndjson: Path | None = None,
    out_stdout: bool = False,
    write_spec_sheet: bool = True,
) -> tuple[int, int, float]:
    """Load questions, run inference, grade, emit atomic JSON. Returns (passed, total, duration_sec)."""
    questions = load_questions(questions_path)
    if not questions:
        print("No questions loaded.", file=sys.stderr)
        return 0, 0, 0.0
    passed = 0
    total = len(questions)
    start = time.perf_counter()
    duration_sec = 0.0
    result_str = "FAIL"
    results: list[dict[str, Any]] = []
    ndjson_handle = None
    if out_ndjson:
        out_ndjson.parent.mkdir(parents=True, exist_ok=True)
        ndjson_handle = open(out_ndjson, "w")

    try:
        for q in questions:
            qid = q.get("id", "unknown")
            prompt = build_prompt(q)
            t0 = time.perf_counter()
            model_answer = call_inference(prompt, qid)
            duration_ms = (time.perf_counter() - t0) * 1000
            correct = grade_answer(q, model_answer)
            if correct:
                passed += 1
            atom = {
                "question_id": qid,
                "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
                "expected_key": q.get("answer_key") or "ABCD"[q.get("answer_index", 0)],
                "model_answer_raw": model_answer[:500] if model_answer else "",
                "model_answer_normalized": normalize_answer(model_answer),
                "correct": correct,
                "duration_ms": round(duration_ms, 3),
            }
            results.append(atom)
            line = json.dumps(atom)
            if out_stdout:
                print(line, flush=True)
            if ndjson_handle:
                ndjson_handle.write(line + "\n")

        duration_sec = time.perf_counter() - start
        result_str = "PASS" if passed == total else "FAIL"

        summary_atom = {
            "summary": True,
            "passed": passed,
            "total": total,
            "duration_sec": round(duration_sec, 6),
            "result": result_str,
        }
        if out_stdout:
            print(json.dumps(summary_atom), flush=True)
        if ndjson_handle:
            ndjson_handle.write(json.dumps(summary_atom) + "\n")
    finally:
        if ndjson_handle:
            ndjson_handle.close()

    # Harness logging: spec-sheet report
    if write_spec_sheet and (HARNESS_DIR / "spec_sheet_metrics.py").exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "spec_sheet_metrics",
                HARNESS_DIR / "spec_sheet_metrics.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            payload = mod.build_spec_sheet(
                ROOT,
                "odin_real_benchmark",
                result_str,
                duration_sec,
                step_timings={"benchmark_sec": duration_sec},
                items_passed=passed,
                items_total=total,
            )
            payload["atomic_output_file"] = str(out_ndjson) if out_ndjson else None
            payload["questions_source"] = str(questions_path or DEFAULT_QUESTIONS_PATH)
            report_path = REPORTS_DIR / "odin_real_benchmark_spec_sheet.json"
            mod.write_spec_sheet_report(report_path, payload)
        except Exception as e:
            print(f"Spec-sheet write skip: {e}", file=sys.stderr)

    return passed, total, duration_sec


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="ODIN real benchmark: MMLU-Pro → inference → grading → atomic JSON")
    ap.add_argument("--questions", type=Path, default=None, help="Path to MMLU-Pro JSON (default: harness/fixtures/mmlu_pro_sample.json)")
    ap.add_argument("--out", type=Path, default=None, help="Write NDJSON to this file (atomic: one JSON object per line)")
    ap.add_argument("--stdout", action="store_true", help="Emit NDJSON to stdout")
    ap.add_argument("--no-spec-sheet", action="store_true", help="Skip writing harness spec-sheet report")
    args = ap.parse_args()
    if not args.out and not args.stdout:
        args.out = REPORTS_DIR / "odin_real_benchmark_atomic.ndjson"
    passed, total, duration_sec = run_benchmark(
        questions_path=args.questions,
        out_ndjson=args.out,
        out_stdout=args.stdout,
        write_spec_sheet=not args.no_spec_sheet,
    )
    if total == 0:
        return 1
    print(f"ODIN real benchmark: {passed}/{total} passed in {duration_sec:.3f}s", file=sys.stderr)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
