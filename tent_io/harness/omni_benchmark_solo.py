#!/usr/bin/env python3
"""
Omni Benchmark Suite — model only, in the box.
No external calls (no network, no subprocess to format/git).
Runs: self-check harness, then all spec modules in parallel.
"""

import json
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "specs"
DOCS_DIR = ROOT / "docs"
HARNESS_DIR = ROOT / "harness"

# Required harness files (self-check)
REQUIRED = [
    ROOT / "docs" / "Phase_18_Omni_Dimensional_Intelligence_Walkthrough.md",
    ROOT / "harness" / "AUDIT_CRITERIA.md",
    ROOT / "harness" / "run_harness.sh",
    ROOT / "specs" / "omnigami_crease_map.json",
]
SPEC_NAMES = [
    "sovereign_omni_lattice",
    "sovereign_logic_omnigami",
    "sovereign_omnigami_assembly",
    "sovereign_multi_brain",
    "sovereign_vigil_standby",
    "sovereign_5d_entanglement",
    "sovereign_entangled_recovery",
    "sovereign_omni_blackout",
]


def check_harness() -> list[str]:
    """Self-check: harness present and complete. No external calls."""
    missing = []
    for p in REQUIRED:
        if not p.exists():
            missing.append(str(p.relative_to(ROOT)))
    return missing


def run_spec(name: str) -> tuple[str, bool, str]:
    """Load and run one spec module. Pure local import/exec, no network."""
    spec_file = SPECS_DIR / f"{name}.py"
    if not spec_file.exists():
        return (name, False, "MISS")
    try:
        sys.path.insert(0, str(SPECS_DIR))
        try:
            with open(spec_file) as f:
                code = compile(f.read(), str(spec_file), "exec")
            exec(code, {"__name__": "__main__"})
        finally:
            if str(SPECS_DIR) in sys.path:
                sys.path.remove(str(SPECS_DIR))
        return (name, True, "OK")
    except Exception as e:
        return (name, False, f"FAIL: {e}")


def run_manifest() -> tuple[str, bool, str]:
    """Validate omnigami manifest. Local file only."""
    path = SPECS_DIR / "omnigami_crease_map.json"
    if not path.exists():
        return ("omnigami_crease_map.json", False, "MISS")
    try:
        with open(path) as f:
            json.load(f)
        return ("omnigami_crease_map.json", True, "OK")
    except Exception as e:
        return ("omnigami_crease_map.json", False, f"FAIL: {e}")


def main() -> int:
    t_start = time.perf_counter()
    step_timings: dict[str, float] = {}

    print("=== Omni Benchmark (solo): model only, no external calls ===")
    print(f"Root: {ROOT}")
    print()

    # 1. Self-check harness
    print("[1/2] Self-check: harness present...")
    t0 = time.perf_counter()
    missing = check_harness()
    step_timings["self_check_sec"] = time.perf_counter() - t0
    if missing:
        for m in missing:
            print(f"  MISS {m}")
        print("  Harness NOT complete.")
        return 1
    print("  OK  harness complete")
    print()

    # 2. Run all specs + manifest in parallel (model alone in the box)
    print("[2/2] Model only (parallel run)...")
    t1 = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(run_spec, n): n for n in SPEC_NAMES}
        futures[ex.submit(run_manifest)] = "manifest"
        for fut in as_completed(futures):
            results.append(fut.result())
    step_timings["model_parallel_sec"] = time.perf_counter() - t1
    results.sort(key=lambda r: r[0])
    fail = 0
    for name, ok, msg in results:
        status = "OK" if ok else "FAIL"
        extra = f"  {msg}" if (not ok and msg and msg != "OK") else ""
        print(f"  {status}  {name}{extra}")
        if not ok:
            fail += 1
    total_duration = time.perf_counter() - t_start
    step_timings["total_sec"] = total_duration
    print()

    # Optional: write enterprise/industrial/military spec-sheet metrics
    if "--json" in sys.argv:
        try:
            spec_sheet = ROOT / "harness" / "spec_sheet_metrics.py"
            if spec_sheet.exists():
                import importlib.util
                load = importlib.util.spec_from_file_location("spec_sheet_metrics", spec_sheet)
                mod = importlib.util.module_from_spec(load)
                load.loader.exec_module(mod)
                payload = mod.build_spec_sheet(
                    ROOT,
                    "omni_benchmark_solo",
                    "PASS" if fail == 0 else "FAIL",
                    total_duration,
                    step_timings=step_timings,
                    items_passed=len([r for r in results if r[1]]),
                    items_total=len(results),
                )
                report_path = ROOT / "harness" / "reports" / "omni_solo_spec_sheet.json"
                mod.write_spec_sheet_report(report_path, payload)
                print(f"Spec-sheet report: {report_path}")
        except Exception as e:
            print(f"Spec-sheet write skip: {e}", file=sys.stderr)

    if fail == 0:
        print("=== Omni Benchmark (solo): PASS ===")
        return 0
    print("=== Omni Benchmark (solo): FAIL ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
