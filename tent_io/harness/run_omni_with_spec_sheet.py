#!/usr/bin/env python3
"""
Run Omni industrial + solo with enterprise/industrial/military spec-sheet metrics.
Writes combined report JSON and prints summary.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "harness" / "reports"


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load metrics builder
    spec_sheet_path = ROOT / "harness" / "spec_sheet_metrics.py"
    import importlib.util
    load = importlib.util.spec_from_file_location("spec_sheet_metrics", spec_sheet_path)
    mod = importlib.util.module_from_spec(load)
    load.loader.exec_module(mod)

    runs = []

    # 1. Industrial suite (subprocess)
    print("=== [1/2] Omni industrial suite ===")
    t0 = time.perf_counter()
    r = subprocess.run(
        [str(ROOT / "harness" / "omni_benchmark_suite.sh"), "--no-format"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    t_ind = time.perf_counter() - t0
    ind_ok = r.returncode == 0
    runs.append({
        "name": "omni_industrial",
        "result": "PASS" if ind_ok else "FAIL",
        "returncode": r.returncode,
        "duration_sec": round(t_ind, 6),
        "duration_ms": round(t_ind * 1000, 3),
    })
    print(r.stdout or "")
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    print(f"Industrial: {'PASS' if ind_ok else 'FAIL'} in {t_ind:.3f}s")
    print()

    # 2. Solo (with --json for spec-sheet)
    print("=== [2/2] Omni solo (model only, --json) ===")
    t1 = time.perf_counter()
    r2 = subprocess.run(
        [sys.executable, str(ROOT / "harness" / "omni_benchmark_solo.py"), "--json"],
        cwd=str(ROOT.parent),  # dev root so tent_io is path
        capture_output=True,
        text=True,
        timeout=60,
    )
    t_solo = time.perf_counter() - t1
    solo_ok = r2.returncode == 0
    runs.append({
        "name": "omni_solo",
        "result": "PASS" if solo_ok else "FAIL",
        "returncode": r2.returncode,
        "duration_sec": round(t_solo, 6),
        "duration_ms": round(t_solo * 1000, 3),
    })
    print(r2.stdout or "")
    if r2.stderr:
        print(r2.stderr, file=sys.stderr)
    print(f"Solo: {'PASS' if solo_ok else 'FAIL'} in {t_solo:.3f}s")
    print()

    # Combined spec sheet (HW/SW once + both runs)
    total_duration = t_ind + t_solo
    sheet = mod.build_spec_sheet(
        ROOT,
        "omni_industrial_and_solo",
        "PASS" if (ind_ok and solo_ok) else "FAIL",
        total_duration,
        step_timings={
            "industrial_sec": t_ind,
            "solo_sec": t_solo,
            "total_sec": total_duration,
        },
        items_passed=2 if (ind_ok and solo_ok) else (1 if (ind_ok or solo_ok) else 0),
        items_total=2,
    )
    sheet["runs"] = runs
    out_path = REPORTS_DIR / "omni_combined_spec_sheet.json"
    mod.write_spec_sheet_report(out_path, sheet)
    print(f"Combined spec-sheet report: {out_path}")

    # Summary
    print()
    print("=== Enterprise / Industrial / Military spec-sheet summary ===")
    print(f"  Hardware: {sheet['hardware'].get('machine', 'N/A')}, {sheet['hardware'].get('cpu_count_logical', 'N/A')} CPUs, {sheet['hardware'].get('ram_gb', 'N/A')} GB RAM")
    print(f"  Software: Python {sheet['software'].get('python_version', 'N/A')[:20]}...")
    print(f"  Industrial: {runs[0]['result']} ({runs[0]['duration_ms']} ms)")
    print(f"  Solo:       {runs[1]['result']} ({runs[1]['duration_ms']} ms)")
    print(f"  Overall:    {sheet['result']}")

    return 0 if (ind_ok and solo_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
