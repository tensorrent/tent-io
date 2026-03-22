#!/usr/bin/env python3
"""Export UPG prime/Ulam projection to MIDI and persistent scroll memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def sha256_obj(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def to_vlq(value: int) -> bytes:
    if value < 0:
        raise ValueError("VLQ value must be non-negative")
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def write_midi(track_events: list[tuple[int, bytes]], out_mid: Path, tpq: int) -> None:
    track_events_sorted = sorted(track_events, key=lambda item: item[0])
    track_data = bytearray()
    prev_tick = 0
    for abs_tick, msg in track_events_sorted:
        delta = abs_tick - prev_tick
        prev_tick = abs_tick
        track_data.extend(to_vlq(delta))
        track_data.extend(msg)
    track_data.extend(to_vlq(0))
    track_data.extend(b"\xFF\x2F\x00")  # end of track

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpq)
    track = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)
    out_mid.write_bytes(header + track)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export UPG record to MIDI persistent memory scroll")
    parser.add_argument(
        "--upg-record",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_training_record.current.json"),
    )
    parser.add_argument(
        "--out-mid",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_prime_pins.current.mid"),
    )
    parser.add_argument(
        "--out-scroll",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_prime_pins_scroll.current.ndjson"),
    )
    parser.add_argument(
        "--out-manifest",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/upg/upg_prime_pins_manifest.current.json"),
    )
    parser.add_argument("--max-points", type=int, default=256)
    parser.add_argument("--ticks-per-step", type=int, default=120)
    parser.add_argument("--tpq", type=int, default=480)
    args = parser.parse_args()

    if not args.upg_record.exists():
        print(json.dumps({"status": "error", "error": "upg_record_missing", "path": str(args.upg_record)}, indent=2))
        return 2

    upg = json.loads(args.upg_record.read_text(encoding="utf-8"))
    proj = upg.get("tensor_torrent_isomorphic_projection", {})
    points = proj.get("points", []) if isinstance(proj, dict) else []
    if not isinstance(points, list):
        points = []
    points = points[: max(0, args.max_points)]

    args.out_mid.parent.mkdir(parents=True, exist_ok=True)
    args.out_scroll.parent.mkdir(parents=True, exist_ok=True)
    args.out_manifest.parent.mkdir(parents=True, exist_ok=True)

    tempo_us_per_quarter = 500000  # 120 BPM
    ms_per_tick = tempo_us_per_quarter / 1000.0 / args.tpq
    base_ts = datetime.fromisoformat(str(upg.get("generated_at_utc", "1970-01-01T00:00:00Z")).replace("Z", "+00:00"))
    if base_ts.tzinfo is None:
        base_ts = base_ts.replace(tzinfo=timezone.utc)

    track_events: list[tuple[int, bytes]] = []
    track_events.append((0, b"\xFF\x51\x03\x07\xA1\x20"))  # tempo meta

    scroll_events: list[dict[str, Any]] = []
    pending_scroll: list[dict[str, Any]] = []
    prev_hash = "0" * 64
    sequence_id = 0

    meta_event = {
        "sequence_id": sequence_id,
        "timestamp_utc": base_ts.isoformat().replace("+00:00", "Z"),
        "channel": 0,
        "message_type": "meta_memory",
        "data": {
            "schema": "tent_io/midi_persistent_memory/v1",
            "upg_record": str(args.upg_record),
            "upg_record_hash": upg.get("record_hash", ""),
            "projection_basis": proj.get("basis", ""),
            "point_count": len(points),
        },
        "prev_hash": prev_hash,
    }
    meta_event["event_hash"] = sha256_obj(meta_event)
    prev_hash = meta_event["event_hash"]
    scroll_events.append(meta_event)
    sequence_id += 1

    for i, point in enumerate(points):
        if not isinstance(point, dict):
            continue
        prime_n = int(point.get("prime_n", 2))
        xy = point.get("ulam_xy", [0, 0])
        x = int(xy[0]) if isinstance(xy, list) and len(xy) > 0 else 0
        y = int(xy[1]) if isinstance(xy, list) and len(xy) > 1 else 0

        channel = (abs(x) + abs(y)) % 16
        note = 21 + (prime_n % 88)  # piano range
        velocity = 35 + (prime_n % 90)
        start_tick = i * args.ticks_per_step + (abs(x) % 4) * 10
        duration_ticks = 90 + (abs(y) % 6) * 20
        end_tick = start_tick + duration_ticks
        cylinder_pin = prime_n % 360

        # MIDI byte events
        track_events.append((start_tick, bytes([0x90 | channel, note, velocity])))
        track_events.append((end_tick, bytes([0x80 | channel, note, 0])))

        pending_scroll.append(
            {
                "tick": start_tick,
                "channel": channel,
                "message_type": "note_on",
                "order": 0,
                "data": {
                    "note": note,
                    "velocity": velocity,
                    "tick": start_tick,
                    "prime_n": prime_n,
                    "ulam_xy": [x, y],
                    "cylinder_pin": cylinder_pin,
                    "path": point.get("path", ""),
                },
            }
        )
        pending_scroll.append(
            {
                "tick": end_tick,
                "channel": channel,
                "message_type": "note_off",
                "order": 1,
                "data": {
                    "note": note,
                    "velocity": 0,
                    "tick": end_tick,
                    "prime_n": prime_n,
                    "ulam_xy": [x, y],
                    "cylinder_pin": cylinder_pin,
                    "path": point.get("path", ""),
                },
            }
        )

    for raw in sorted(pending_scroll, key=lambda e: (int(e["tick"]), int(e["order"]))):
        tick = int(raw["tick"])
        ts = (base_ts + timedelta(milliseconds=int(round(tick * ms_per_tick)))).isoformat().replace("+00:00", "Z")
        event = {
            "sequence_id": sequence_id,
            "timestamp_utc": ts,
            "channel": int(raw["channel"]),
            "message_type": str(raw["message_type"]),
            "data": raw["data"],
            "prev_hash": prev_hash,
        }
        event["event_hash"] = sha256_obj(event)
        prev_hash = event["event_hash"]
        scroll_events.append(event)
        sequence_id += 1

    write_midi(track_events, args.out_mid, args.tpq)

    with args.out_scroll.open("w", encoding="utf-8") as f:
        for event in scroll_events:
            f.write(json.dumps(event, ensure_ascii=True))
            f.write("\n")

    manifest = {
        "schema": "tent_io/upg_midi_scroll_manifest/v1",
        "upg_record": str(args.upg_record),
        "upg_record_hash": upg.get("record_hash", ""),
        "midi_file": str(args.out_mid),
        "midi_sha256": hashlib.sha256(args.out_mid.read_bytes()).hexdigest(),
        "scroll_file": str(args.out_scroll),
        "scroll_sha256": hashlib.sha256(args.out_scroll.read_bytes()).hexdigest(),
        "scroll_events": len(scroll_events),
        "pins_written": len(points),
        "ticks_per_step": args.ticks_per_step,
        "tpq": args.tpq,
        "message_types": ["meta_memory", "note_on", "note_off"],
    }
    manifest["manifest_hash"] = sha256_obj(manifest)
    args.out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "upg_record": str(args.upg_record),
                "out_mid": str(args.out_mid),
                "out_scroll": str(args.out_scroll),
                "out_manifest": str(args.out_manifest),
                "pins_written": len(points),
                "scroll_events": len(scroll_events),
                "manifest_hash": manifest["manifest_hash"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
