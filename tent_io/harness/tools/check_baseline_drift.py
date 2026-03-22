#!/usr/bin/env python3
"""Fail when challenger best profile changes baseline without approval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing JSON: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return payload


def extract_profile_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("name", "profile"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
    return None


def best_profile_name(payload: dict[str, Any]) -> str | None:
    best = payload.get("best_profile")
    return extract_profile_name(best)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check baseline profile stability")
    parser.add_argument("--current", type=Path, required=True, help="Current baseline pointer JSON.")
    parser.add_argument("--challenger", type=Path, required=True, help="Candidate sweep/baseline-change JSON.")
    parser.add_argument(
        "--allow-change",
        action="store_true",
        help="Allow baseline profile changes without failing.",
    )
    args = parser.parse_args()

    current = load_json(args.current)
    challenger = load_json(args.challenger)

    current_best = best_profile_name(current)
    challenger_best = best_profile_name(challenger)

    if current_best is None or challenger_best is None:
        out = {
            "status": "skipped",
            "reason": "missing_best_profile",
            "current_best_profile": current_best,
            "challenger_best_profile": challenger_best,
            "allow_change": args.allow_change,
        }
        print(json.dumps(out, indent=2, ensure_ascii=True))
        return 0

    changed = current_best != challenger_best

    out = {
        "status": "ok",
        "current_best_profile": current_best,
        "challenger_best_profile": challenger_best,
        "baseline_changed": changed,
        "allow_change": args.allow_change,
    }

    if changed and not args.allow_change:
        out["status"] = "alarm"
        out["reason"] = "baseline_changed_without_approval"
        print(json.dumps(out, indent=2, ensure_ascii=True))
        return 7

    print(json.dumps(out, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
