#!/usr/bin/env python3
"""
Watch system resources in the terminal (refresh every --interval seconds).
CPU, memory (RAM), process RSS; optional disk. Uses stdlib + subprocess;
optional psutil for CPU percent. No external network.
"""

import argparse
import os
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _run(cmd: list[str], timeout: int = 2) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def mem_macos() -> dict:
    out = {}
    raw = _run(["vm_stat"])
    if not raw:
        return out
    # First line may be "Mach Virtual Memory Statistics: (page size of 16384 bytes)"
    page_size = 4096
    for line in raw.splitlines():
        if "page size of" in line.lower():
            try:
                page_size = int(line.split("page size of")[1].split("bytes")[0].strip())
            except (IndexError, ValueError):
                pass
            continue
        line = line.strip().rstrip(".")
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().replace(" ", "_").replace("-", "_").lower()
        try:
            out[key] = int(val.strip()) * page_size
        except ValueError:
            continue
    out["_page_size"] = page_size
    return out


def mem_linux() -> dict:
    out = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                key = parts[0].rstrip(":").lower()
                # value in kB
                out[key] = int(parts[1]) * 1024
    except Exception:
        pass
    return out


def format_bytes(n: int) -> str:
    if n is None or n < 0:
        return "—"
    if n >= 1024**3:
        return f"{n / 1024**3:.2f} GB"
    if n >= 1024**2:
        return f"{n / 1024**2:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def get_cpu_count() -> int:
    return os.cpu_count() or 0


def get_cpu_percent() -> float | None:
    try:
        import psutil
        return psutil.cpu_percent(interval=0.1)
    except ImportError:
        pass
    # macOS: sysctl doesn't give instant load; skip or use last line of top
    return None


def get_process_rss() -> int | None:
    try:
        ru = resource.getrusage(resource.RUSAGE_SELF)
        return getattr(ru, "ru_maxrss", None)  # macOS bytes, Linux often KB
    except Exception:
        return None


def get_disk_usage(path: str = ".") -> tuple[int, int, int] | None:
    try:
        import psutil
        du = psutil.disk_usage(path)
        return (du.total, du.used, du.free)
    except Exception:
        return None


def sample(interval_sec: float) -> dict:
    data = {
        "utc": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        "cpu_count": get_cpu_count(),
        "cpu_percent": get_cpu_percent(),
        "process_rss": get_process_rss(),
        "mem": {},
        "disk": None,
    }
    if sys.platform == "darwin":
        data["mem"] = mem_macos()
    elif sys.platform == "linux":
        data["mem"] = mem_linux()
    du = get_disk_usage()
    if du:
        data["disk"] = {"total": du[0], "used": du[1], "free": du[2]}
    return data


def print_snapshot(data: dict, show_disk: bool) -> None:
    lines = [
        f"  Resources @ {data['utc']}",
        f"  CPU: {data['cpu_count']} logical cores" + (
            f"  |  load: {data['cpu_percent']:.1f}%" if data.get("cpu_percent") is not None else ""
        ),
    ]
    mem = data.get("mem") or {}
    if sys.platform == "darwin" and mem:
        # vm_stat: page counts; total ≈ active + inactive + wired + free + speculative
        total = (mem.get("pages_wired_down", 0) + mem.get("pages_active", 0)
                 + mem.get("pages_inactive", 0) + mem.get("pages_free", 0)
                 + mem.get("pages_speculative", 0))
        if total:
            used = total - mem.get("pages_free", 0) - mem.get("pages_speculative", 0)
            lines.append(f"  RAM: {format_bytes(used)} / ~{format_bytes(total)} used")
        else:
            lines.append(f"  RAM: {format_bytes(mem.get('pages_free', 0))} free (see vm_stat)")
    elif sys.platform == "linux" and mem:
        total = mem.get("memtotal", 0)
        avail = mem.get("memavailable", mem.get("memfree", 0))
        if total:
            lines.append(f"  RAM: {format_bytes(total - avail)} / {format_bytes(total)} used")
    else:
        lines.append("  RAM: (no data)")
    rss = data.get("process_rss")
    if rss is not None:
        # Linux reports KB in some versions
        if rss < 1024 * 1024 and sys.platform == "linux":
            rss = rss * 1024
        lines.append(f"  Process RSS: {format_bytes(rss)}")
    if show_disk and data.get("disk"):
        d = data["disk"]
        pct = 100 * d["used"] / d["total"] if d["total"] else 0
        lines.append(f"  Disk: {format_bytes(d['used'])} / {format_bytes(d['total'])} ({pct:.0f}% used)")
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description="Watch system resources (CPU, RAM, process, optional disk).")
    ap.add_argument("-n", "--interval", type=float, default=2.0, help="Refresh interval (seconds)")
    ap.add_argument("-d", "--disk", action="store_true", help="Show disk usage (requires psutil)")
    ap.add_argument("--once", action="store_true", help="Print once and exit (no watch loop)")
    args = ap.parse_args()
    if args.once:
        print_snapshot(sample(0), args.disk)
        return 0
    try:
        while True:
            # Clear line area (simple: print newlines then cursor up; or use clear screen)
            data = sample(args.interval)
            print("\033[2J\033[H", end="")  # clear and home cursor
            print_snapshot(data, args.disk)
            print("\n  (Ctrl+C to stop)")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
