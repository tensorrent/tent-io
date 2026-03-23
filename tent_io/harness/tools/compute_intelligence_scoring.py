#!/usr/bin/env python3
"""Compute ML/AI/AGI-oriented intelligence scoring from expansion artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# tools/ is not a package; load core from parent harness directory
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from intelligence_scoring_core import build_intelligence_scoring_output  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute intelligence scoring and logic-chain quality metrics")
    parser.add_argument("--sweep-summary", type=Path, required=True)
    parser.add_argument("--external-compare", type=Path, required=False, default=None)
    parser.add_argument("--promotion-decision", type=Path, required=False, default=None)
    parser.add_argument("--promotion-trend", type=Path, required=False, default=None)
    parser.add_argument(
        "--scoring-preset",
        choices=("default", "conversation_focused"),
        default="default",
        help="Weight preset for ml/logic scores (default matches original weights).",
    )
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    args = parser.parse_args()

    sweep = load_json(args.sweep_summary)
    external = load_json(args.external_compare) if args.external_compare else {}
    decision = load_json(args.promotion_decision) if args.promotion_decision else {}
    trend = load_json(args.promotion_trend) if args.promotion_trend else {}

    out = build_intelligence_scoring_output(
        sweep,
        external=external,
        decision=decision,
        trend=trend,
        scoring_preset=args.scoring_preset,
    )
    out["inputs"] = {
        "sweep_summary": str(args.sweep_summary),
        "external_compare": str(args.external_compare) if args.external_compare else None,
        "promotion_decision": str(args.promotion_decision) if args.promotion_decision else None,
        "promotion_trend": str(args.promotion_trend) if args.promotion_trend else None,
    }

    best = sweep.get("best_profile") if isinstance(sweep.get("best_profile"), dict) else {}
    internal_profile = best.get("profile") if isinstance(best.get("profile"), str) else None
    decision_state = out.get("decision_state")
    scores = out.get("scores") if isinstance(out.get("scores"), dict) else {}
    ext_favored = out.get("components", {}).get("external", {}).get("favored_profile")
    contested = out.get("components", {}).get("governance", {}).get("contested_ratio_recent")

    lines = [
        "# Intelligence Scoring",
        "",
        f"- scoring_preset: `{args.scoring_preset}`",
        f"- scoring_version: `{out.get('scoring_version')}`",
        f"- internal_profile: `{internal_profile}`",
        f"- decision_state: `{decision_state}`",
        f"- promotion_allowed: `{out.get('promotion_allowed')}`",
        f"- ml_intelligence_score: `{scores.get('ml_intelligence_score')}`",
        f"- logic_chain_score: `{scores.get('logic_chain_score')}`",
        f"- ai_intelligence_score: `{scores.get('ai_intelligence_score')}`",
        f"- agi_readiness_score: `{scores.get('agi_readiness_score')}`",
        f"- external_favored_profile: `{ext_favored}`",
        f"- contested_ratio_recent: `{contested}`",
    ]

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out_json": str(args.out_json), "out_md": str(args.out_md)}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
