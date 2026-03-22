#!/usr/bin/env python3
"""
Enterprise / Industrial / Military spec-sheet metrics capture.
Traceable, reproducible: HW, SW, model, run timing, config integrity (hashes).
No external network; local only.
"""

import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def capture_hardware() -> dict[str, Any]:
    """Hardware: CPU, memory, platform per enterprise/industrial spec."""
    out: dict[str, Any] = {
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "cpu_count_logical": os.cpu_count(),
    }
    # RAM (macOS / Linux)
    try:
        if sys.platform == "darwin":
            r = __import__("subprocess").run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if r.returncode == 0:
                out["ram_bytes"] = int(r.stdout.strip())
                out["ram_gb"] = round(out["ram_bytes"] / (1024**3), 4)
        elif sys.platform == "linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        out["ram_kb"] = int(line.split()[1])
                        out["ram_gb"] = round(out["ram_kb"] / (1024 * 1024), 4)
                        break
    except Exception:
        pass
    return out


def capture_software() -> dict[str, Any]:
    """Software: interpreter, version, executable."""
    return {
        "python_version": sys.version,
        "python_version_info": list(sys.version_info),
        "python_executable": sys.executable,
        "platform_python_implementation": platform.python_implementation(),
    }


def capture_process_memory() -> dict[str, Any]:
    """Process memory (RSS if available) for run-time footprint."""
    out: dict[str, Any] = {}
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF)
        # maxrss on macOS is bytes; on Linux often KB
        out["max_rss_bytes"] = getattr(ru, "ru_maxrss", None)
    except Exception:
        pass
    return out


def file_sha256(path: Path) -> str:
    """SHA-256 of file content for config/manifest integrity."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def capture_config_integrity(root: Path) -> dict[str, Any]:
    """Integrity hashes for critical config/artifact files (reproducibility)."""
    out: dict[str, Any] = {}
    candidates = [
        root / "specs" / "omnigami_crease_map.json",
        root / "harness" / "AUDIT_CRITERIA.md",
        root / "harness" / "run_harness.sh",
    ]
    for p in candidates:
        if p.exists():
            try:
                out[p.name] = file_sha256(p)
            except Exception:
                out[p.name] = None
    return out


def capture_sparsity() -> dict[str, Any]:
    """SparsePlug sparsity target (env or RAM-based). See harness/sparseplug_sparsity.py."""
    try:
        spec_dir = Path(__file__).resolve().parent
        if (spec_dir / "sparseplug_sparsity.py").exists():
            import importlib.util
            load = importlib.util.spec_from_file_location(
                "sparseplug_sparsity",
                spec_dir / "sparseplug_sparsity.py",
            )
            mod = importlib.util.module_from_spec(load) if load.loader else None
            if mod is not None and load.loader is not None:
                load.loader.exec_module(mod)
            if mod and hasattr(mod, "get_sparsity_target"):
                target, source = mod.get_sparsity_target()
                return {"sparseplug_target": round(target, 4), "sparseplug_source": source}
    except Exception:
        pass
    return {"sparseplug_target": None, "sparseplug_source": "unavailable"}


def build_spec_sheet(
    root: Path,
    run_name: str,
    result: str,
    duration_sec: float,
    step_timings: dict[str, float] | None = None,
    items_passed: int | None = None,
    items_total: int | None = None,
) -> dict[str, Any]:
    """Build full enterprise/industrial/military spec-sheet payload."""
    return {
        "spec_sheet_version": "1.0",
        "classification": "enterprise_industrial_military_metrics",
        "capture_utc": _utc_iso(),
        "run_name": run_name,
        "result": result,
        "duration_sec": round(duration_sec, 6),
        "duration_ms": round(duration_sec * 1000, 3),
        "items_passed": items_passed,
        "items_total": items_total,
        "step_timings_sec": step_timings or {},
        "hardware": capture_hardware(),
        "software": capture_software(),
        "process_memory": capture_process_memory(),
        "sparsity": capture_sparsity(),
        "config_integrity": capture_config_integrity(root),
        "cwd": str(Path.cwd()),
        "root": str(root),
    }


def write_spec_sheet_report(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON report to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


if __name__ == "__main__":
    # Quick test: capture only
    ROOT = Path(__file__).resolve().parent.parent
    sheet = build_spec_sheet(ROOT, "metrics_test", "OK", 0.0)
    print(json.dumps(sheet, indent=2))
