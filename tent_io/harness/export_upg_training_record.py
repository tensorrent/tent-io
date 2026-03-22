#!/usr/bin/env python3
"""Export deterministic training/teaching record for UPG ingestion."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_obj(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return sha256_bytes(data)


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0:
        return False
    f = 3
    while f * f <= n:
        if n % f == 0:
            return False
        f += 2
    return True


def first_primes(count: int) -> list[int]:
    out: list[int] = []
    x = 2
    while len(out) < count:
        if is_prime(x):
            out.append(x)
        x += 1
    return out


def ulam_xy(n: int) -> tuple[int, int]:
    if n <= 1:
        return (0, 0)
    x = 0
    y = 0
    step = 1
    cur = 1
    while cur < n:
        for _ in range(step):
            if cur >= n:
                break
            x += 1
            cur += 1
        for _ in range(step):
            if cur >= n:
                break
            y += 1
            cur += 1
        step += 1
        for _ in range(step):
            if cur >= n:
                break
            x -= 1
            cur += 1
        for _ in range(step):
            if cur >= n:
                break
            y -= 1
            cur += 1
        step += 1
    return (x, y)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_training_reports(training_dir: Path, limit: int) -> list[Path]:
    files = sorted(training_dir.glob("*/report.json"))
    if not files:
        return []
    return files[-limit:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export UPG training/teaching compression record")
    parser.add_argument(
        "--pipeline-report",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/full_stage_pipeline.current.json"),
    )
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/training"),
    )
    parser.add_argument("--training-report-limit", type=int, default=12)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_training_record.current.json"),
    )
    parser.add_argument(
        "--out-gzip",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_training_record.current.json.gz"),
    )
    args = parser.parse_args()

    if not args.pipeline_report.exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "pipeline_report_missing",
                    "pipeline_report": str(args.pipeline_report),
                },
                indent=2,
            )
        )
        return 2

    pipe = read_json(args.pipeline_report)
    stages = pipe.get("stages", {})
    if not isinstance(stages, dict):
        stages = {}

    references: list[dict[str, Any]] = []
    missing_refs: list[str] = []

    for stage_name, stage_val in stages.items():
        if not isinstance(stage_val, dict):
            continue
        stdout = stage_val.get("stdout")
        if not isinstance(stdout, str):
            continue
        try:
            payload = json.loads(stdout)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        out_path = payload.get("out")
        if not isinstance(out_path, str):
            continue
        p = Path(out_path)
        if not p.exists():
            missing_refs.append(out_path)
            continue
        digest = sha256_bytes(p.read_bytes())
        references.append(
            {
                "source": stage_name,
                "path": str(p),
                "sha256": digest,
                "bytes": p.stat().st_size,
            }
        )

    for report_file in collect_training_reports(args.training_dir, args.training_report_limit):
        digest = sha256_bytes(report_file.read_bytes())
        references.append(
            {
                "source": "training_report",
                "path": str(report_file),
                "sha256": digest,
                "bytes": report_file.stat().st_size,
            }
        )

    references = sorted(references, key=lambda x: (str(x["source"]), str(x["path"])))
    ref_hash = sha256_obj(references)

    primes = first_primes(4096)
    lattice_points: list[dict[str, Any]] = []
    for ref in references:
        h = str(ref["sha256"])
        n = int(h[:16], 16)
        p = primes[n % len(primes)]
        x, y = ulam_xy(p)
        lattice_points.append(
            {
                "path": ref["path"],
                "prime_n": p,
                "ulam_xy": [x, y],
            }
        )

    deterministic_inputs = {
        "pipeline_report": str(args.pipeline_report),
        "training_dir": str(args.training_dir),
        "training_report_limit": args.training_report_limit,
        "references_hash": ref_hash,
    }
    deterministic_inputs_hash = sha256_obj(deterministic_inputs)

    out_payload: dict[str, Any] = {
        "schema": "tent_io/upg_training_record/v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pipeline_run_id": pipe.get("run_id"),
        "pipeline_status": pipe.get("status"),
        "deterministic_inputs_hash": deterministic_inputs_hash,
        "references_hash": ref_hash,
        "reference_count": len(references),
        "missing_reference_count": len(missing_refs),
        "missing_references": missing_refs,
        "references": references,
        "tensor_torrent_isomorphic_projection": {
            "basis": "prime_distribution_on_ulam_spiral",
            "point_count": len(lattice_points),
            "points": lattice_points,
        },
    }
    out_payload["record_hash"] = sha256_obj(out_payload)

    raw = json.dumps(out_payload, indent=2, ensure_ascii=True).encode("utf-8")
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_bytes(raw)
    with args.out_gzip.open("wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(raw)
    gzip_digest = sha256_bytes(args.out_gzip.read_bytes())

    print(
        json.dumps(
            {
                "status": "ok",
                "out": str(args.out_json),
                "out_gzip": str(args.out_gzip),
                "reference_count": len(references),
                "record_hash": out_payload["record_hash"],
                "gzip_sha256": gzip_digest,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
