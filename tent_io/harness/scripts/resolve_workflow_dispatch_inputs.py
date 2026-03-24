#!/usr/bin/env python3
"""
Emit GITHUB_ENV lines INPUTS_<KEY>=<value> for tent-io-llt-expansion.yml.

- workflow_dispatch: values from github.event.inputs (strings; booleans as true/false).
- pull_request (and other events): use the same defaults as workflow_dispatch in the YAML.

Scope: mirrors defaults in .github/workflows/tent-io-llt-expansion.yml (keep in sync on input changes).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


# Defaults must match workflow_dispatch `default:` for each input (RC1: single source of truth in YAML).
DEFAULTS: dict[str, str | bool] = {
    "profiles": "auto_top2",
    "query": "system profile check",
    "expansion_rank_by": "mmlu_test_acc",
    "run_auto_all_compare": False,
    "min_best_final_test_acc": "0.20",
    "min_delta_vs_previous_best": "",
    "promotion_history_keep_last": "",
    "promotion_summary_top_k": "3",
    "promotion_summary_sort_by": "promotions",
    "promotion_summary_history_window": "",
    "trend_window": "5",
    "trend_window_long": "20",
    "leaderboard_window": "10",
    "split_gate_profile": "off",
    "enable_external_eval": True,
    "allow_baseline_change": False,
    "enforce_promotion_decision_policy": False,
    "enforce_intelligence_promotion_advisory": False,
    "intelligence_advisory_required_streak": "2",
    "regression_min_delta_final_test_acc": "-0.01",
    "regression_min_delta_mmlu_test_acc": "-0.01",
    "regression_min_delta_conversational_test_acc": "-0.02",
    "regression_max_delta_drift": "0.0",
    "promotion_alignment_required_runs": "2",
    "promotion_min_internal_margin": "0.0",
    "promotion_min_external_vote_margin": "0",
    "contested_external_tie_break": False,
    "contested_external_margin_threshold": "0.02",
    "contested_external_tie_break_streak": "3",
    "tie_break_adaptive_threshold": False,
    "tie_break_use_effective_confidence": False,
    "tie_break_effective_confidence_threshold": "",
    "tie_break_hysteresis_enable": False,
    "tie_break_hysteresis_high": "",
    "tie_break_hysteresis_low": "",
    "tie_break_hysteresis_upward_only": False,
    "tie_break_stability_gate": False,
    "tie_break_stability_require_upward_crossing": False,
    "tie_break_stability_max_abs_acceleration": "",
    "tie_break_stability_max_near_boundary_streak": "",
    "tie_break_stability_near_epsilon": "0.05",
    "tie_break_stability_history_tail": "64",
    "tie_break_oscillation_amplitude_band": "0.2",
    "enforce_intelligence_readiness": False,
    "intelligence_min_ml_score": "",
    "intelligence_min_logic_chain_score": "",
    "intelligence_min_ai_score": "",
    "intelligence_min_agi_readiness_score": "",
    "intelligence_max_contested_ratio": "",
    "intelligence_allowed_decision_states": "",
    "intelligence_scoring_preset": "default",
    "enforce_intelligence_regression": False,
    "intelligence_min_delta_ml_score": "",
    "intelligence_min_delta_logic_chain_score": "",
    "intelligence_min_delta_ai_score": "",
    "intelligence_min_delta_agi_readiness_score": "",
    "intelligence_max_delta_contested_ratio": "",
    "enforce_intelligence_regression_trend": False,
    "intelligence_regression_trend_window": "10",
    "intelligence_regression_max_alarm_ratio": "",
    "intelligence_regression_max_consecutive_alarms": "",
}


def _env_name(key: str) -> str:
    return "INPUTS_" + key.upper()


def _as_string(v: str | bool | None) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def main() -> int:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    gh_env = os.environ.get("GITHUB_ENV")

    if not gh_env:
        print("resolve_workflow_dispatch_inputs: GITHUB_ENV not set; skipping.", file=sys.stderr)
        return 0

    merged: dict[str, str | bool] = dict(DEFAULTS)

    if event_name == "workflow_dispatch" and event_path:
        p = Path(event_path)
        if p.is_file():
            ev = json.loads(p.read_text(encoding="utf-8"))
            raw = ev.get("inputs") or {}
            for k in DEFAULTS:
                if k in raw and raw[k] is not None:
                    val = raw[k]
                    if isinstance(val, bool):
                        merged[k] = val
                    elif isinstance(val, str):
                        if k in (
                            "run_auto_all_compare",
                            "enable_external_eval",
                            "allow_baseline_change",
                            "enforce_promotion_decision_policy",
                            "enforce_intelligence_promotion_advisory",
                            "contested_external_tie_break",
                            "tie_break_adaptive_threshold",
                            "tie_break_use_effective_confidence",
                            "tie_break_hysteresis_enable",
                            "tie_break_hysteresis_upward_only",
                            "tie_break_stability_gate",
                            "tie_break_stability_require_upward_crossing",
                            "enforce_intelligence_readiness",
                            "enforce_intelligence_regression",
                            "enforce_intelligence_regression_trend",
                        ):
                            merged[k] = val == "true"
                        else:
                            merged[k] = val
                    else:
                        merged[k] = val

    lines: list[str] = []
    for key in DEFAULTS:
        lines.append(f"{_env_name(key)}={_as_string(merged.get(key))}")

    with open(gh_env, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
