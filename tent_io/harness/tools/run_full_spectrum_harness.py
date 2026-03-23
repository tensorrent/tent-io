#!/usr/bin/env python3
"""
Run the full-spectrum harness: unit tests + scoring fixture validation.

Exits non-zero if any unittest fails. Writes a JSON report under harness/reports/.
No external services required (stdlib only for tests).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from intelligence_scoring_core import build_intelligence_scoring_output  # noqa: E402


def run_unittest_suite(test_dir: Path) -> tuple[int, str]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(test_dir), pattern="test_*.py", top_level_dir=str(test_dir))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    buf = []
    for err in result.errors:
        buf.append(f"ERROR {err[0]}: {err[1]}")
    for fail in result.failures:
        buf.append(f"FAIL {fail[0]}: {fail[1]}")
    text = "\n".join(buf) if buf else "ok"
    code = 0 if result.wasSuccessful() else 1
    return code, text


def validate_fixture_sweep(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = build_intelligence_scoring_output(data, scoring_preset="default")
    scores = out.get("scores") if isinstance(out.get("scores"), dict) else {}
    required = (
        "ml_intelligence_score",
        "logic_chain_score",
        "ai_intelligence_score",
        "agi_readiness_score",
    )
    missing = [k for k in required if k not in scores]
    return {
        "fixture_path": str(path),
        "status": "ok" if not missing else "alarm",
        "missing_score_keys": missing,
        "scoring_version": out.get("scoring_version"),
        "scores": scores,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Full-spectrum harness: tests + scoring fixture check")
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Only validate the fixture JSON against intelligence_scoring_core.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Optional sweep JSON (default: harness/tests/fixtures/sweep_full_spectrum.json).",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Default: tent_io/harness/reports/full_spectrum_harness.current.json",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[3]
    test_dir = repo / "tent_io" / "harness" / "tests"
    fixture = args.fixture or (test_dir / "fixtures" / "sweep_full_spectrum.json")
    out_json = args.out_json or (repo / "tent_io" / "harness" / "reports" / "full_spectrum_harness.current.json")

    test_code = 0
    test_summary = "skipped"
    if not args.skip_tests:
        test_code, test_summary = run_unittest_suite(test_dir)

    fixture_report = {}
    if fixture.exists():
        fixture_report = validate_fixture_sweep(fixture)
    else:
        fixture_report = {"fixture_path": str(fixture), "status": "skipped", "reason": "file_not_found"}

    report = {
        "status": "ok" if test_code == 0 and fixture_report.get("status") != "alarm" else "alarm",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unittest_exit_code": test_code,
        "unittest_summary": test_summary,
        "fixture_validation": fixture_report,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return test_code if test_code else (1 if report["status"] == "alarm" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
