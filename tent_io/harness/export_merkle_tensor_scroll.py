#!/usr/bin/env python3
"""Build Merkle bit-hash map from persistent MIDI scroll memory."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_hex(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))


def pair_hash(left_hex: str, right_hex: str) -> str:
    return sha256_hex(bytes.fromhex(left_hex) + bytes.fromhex(right_hex))


def merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return "0" * 64
    level = list(leaves)
    while len(level) > 1:
        nxt: list[str] = []
        for i in range(0, len(level), 2):
            l = level[i]
            r = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(pair_hash(l, r))
        level = nxt
    return level[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Merkle bit-hash tensor scroll map")
    parser.add_argument(
        "--scroll",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_prime_pins_scroll.current.ndjson"),
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_merkle_tensor_scroll.current.json"),
    )
    parser.add_argument(
        "--out-wireframe",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_merkle_tensor_scroll_wireframe.current.md"),
    )
    parser.add_argument("--bucket-prefix-bits", type=int, default=8)
    parser.add_argument("--reuse-cache", action="store_true", help="Reuse prior map when scroll hash is unchanged.")
    args = parser.parse_args()

    if not args.scroll.exists():
        print(json.dumps({"status": "error", "error": "scroll_missing", "scroll": str(args.scroll)}, indent=2))
        return 2

    scroll_bytes = args.scroll.read_bytes()
    scroll_sha256 = sha256_hex(scroll_bytes)

    if args.reuse_cache and args.out_json.exists():
        try:
            prev = json.loads(args.out_json.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
        if isinstance(prev, dict) and prev.get("scroll_sha256") == scroll_sha256:
            if not args.out_wireframe.exists():
                root = str(prev.get("merkle_root", ""))
                head = str(prev.get("hash_chain_head", ""))
                wc = bool(prev.get("invariants", {}).get("hash_chain_valid", False)) if isinstance(prev.get("invariants"), dict) else False
                args.out_wireframe.parent.mkdir(parents=True, exist_ok=True)
                args.out_wireframe.write_text(
                    "\n".join(
                        [
                            "# UPG Merkle Tensor Scroll Wireframe",
                            "",
                            "## Invariant frame",
                            "",
                            f"- `scroll_sha256`: `{scroll_sha256}`",
                            f"- `merkle_root`: `{root}`",
                            f"- `hash_chain_head`: `{head}`",
                            f"- `hash_chain_valid`: `{wc}`",
                            "",
                            "Generated during cache reuse path.",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "mode": "cache_reuse",
                        "out": str(args.out_json),
                        "out_wireframe": str(args.out_wireframe),
                        "scroll_sha256": scroll_sha256,
                        "merkle_root": prev.get("merkle_root", ""),
                        "leaf_count": prev.get("leaf_count", 0),
                    },
                    indent=2,
                )
            )
            return 0

    lines = [ln for ln in args.scroll.read_text(encoding="utf-8").splitlines() if ln.strip()]
    events: list[dict[str, Any]] = []
    for ln in lines:
        events.append(json.loads(ln))

    # Invariant checks
    invariant_errors: list[str] = []
    expected_prev = "0" * 64
    leaves: list[str] = []
    for idx, ev in enumerate(events):
        if not isinstance(ev, dict):
            invariant_errors.append(f"event_{idx}_not_object")
            continue
        received_prev = str(ev.get("prev_hash", ""))
        if received_prev != expected_prev:
            invariant_errors.append(f"prev_hash_mismatch_at_{idx}")
        tmp = dict(ev)
        received_hash = str(tmp.pop("event_hash", ""))
        computed_hash = sha256_obj(tmp)
        if received_hash != computed_hash:
            invariant_errors.append(f"event_hash_mismatch_at_{idx}")
        expected_prev = received_hash
        leaves.append(received_hash)

    root = merkle_root(leaves)
    prefix_hex_len = max(1, args.bucket_prefix_bits // 4)
    buckets: dict[str, dict[str, Any]] = {}
    for leaf in leaves:
        key = leaf[:prefix_hex_len]
        bucket = buckets.setdefault(key, {"count": 0, "xor64": 0})
        bucket["count"] += 1
        bucket["xor64"] ^= int(leaf[-16:], 16)

    bucket_rows: list[dict[str, Any]] = []
    for k in sorted(buckets):
        row = buckets[k]
        bucket_rows.append(
            {
                "prefix": k,
                "count": int(row["count"]),
                "xor64_hex": f"{int(row['xor64']) & ((1 << 64) - 1):016x}",
            }
        )

    # Extract memory instructions for synthesis/replay.
    memory_instructions: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("message_type") == "meta_memory":
            data = ev.get("data", {})
            if isinstance(data, dict):
                memory_instructions.append(
                    {
                        "instruction": "seed_upg_projection",
                        "projection_basis": data.get("projection_basis", ""),
                        "upg_record_hash": data.get("upg_record_hash", ""),
                        "point_count": data.get("point_count", 0),
                    }
                )
        elif ev.get("message_type") in ("note_on", "note_off"):
            data = ev.get("data", {})
            if isinstance(data, dict):
                memory_instructions.append(
                    {
                        "instruction": "replay_pin_event",
                        "message_type": ev.get("message_type", ""),
                        "prime_n": data.get("prime_n"),
                        "cylinder_pin": data.get("cylinder_pin"),
                        "ulam_xy": data.get("ulam_xy"),
                        "path": data.get("path", ""),
                    }
                )

    out_payload: dict[str, Any] = {
        "schema": "tent_io/upg_merkle_tensor_scroll/v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scroll_path": str(args.scroll),
        "scroll_sha256": scroll_sha256,
        "leaf_count": len(leaves),
        "merkle_root": root,
        "hash_chain_head": leaves[-1] if leaves else ("0" * 64),
        "bucket_prefix_bits": args.bucket_prefix_bits,
        "bucket_count": len(bucket_rows),
        "bit_hash_buckets": bucket_rows,
        "invariants": {
            "hash_chain_valid": all("prev_hash_mismatch" not in e and "event_hash_mismatch" not in e for e in invariant_errors),
            "errors": invariant_errors,
        },
        "synthesis": {
            "strategy": "persistent_merkle_replay",
            "instructions": memory_instructions,
            "instruction_count": len(memory_instructions),
            "note": "Replay previous Merkle-pinned events before adding new events.",
        },
    }
    out_payload["map_hash"] = sha256_obj(out_payload)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_wireframe.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out_payload, indent=2, ensure_ascii=True), encoding="utf-8")

    wireframe = f"""# UPG Merkle Tensor Scroll Wireframe

## Invariant frame

- `scroll_sha256`: `{scroll_sha256}`
- `leaf_count`: `{len(leaves)}`
- `merkle_root`: `{root}`
- `hash_chain_head`: `{out_payload["hash_chain_head"]}`
- `hash_chain_valid`: `{out_payload["invariants"]["hash_chain_valid"]}`

## Bit-hash map

- `bucket_prefix_bits`: `{args.bucket_prefix_bits}`
- `bucket_count`: `{len(bucket_rows)}`
- `map_hash`: `{out_payload["map_hash"]}`

## Synthesis instructions

1. Read persistent scroll and verify hash-chain continuity.
2. Build/verify Merkle root from ordered `event_hash` leaves.
3. Reuse prior memory if `scroll_sha256` and `merkle_root` are unchanged.
4. Replay `meta_memory` seed event.
5. Replay `note_on`/`note_off` pin events as deterministic training context.
6. Append only new events; never rewrite prior leaves.
7. Recompute root and persist updated map + wireframe.

This file is generated from `tent_io/harness/export_merkle_tensor_scroll.py`.
"""
    args.out_wireframe.write_text(wireframe, encoding="utf-8")

    status = "ok" if not invariant_errors else "warning"
    print(
        json.dumps(
            {
                "status": status,
                "out": str(args.out_json),
                "out_wireframe": str(args.out_wireframe),
                "scroll_sha256": scroll_sha256,
                "leaf_count": len(leaves),
                "merkle_root": root,
                "hash_chain_valid": out_payload["invariants"]["hash_chain_valid"],
                "errors": invariant_errors,
            },
            indent=2,
        )
    )
    return 0 if status == "ok" else 3


if __name__ == "__main__":
    raise SystemExit(main())
