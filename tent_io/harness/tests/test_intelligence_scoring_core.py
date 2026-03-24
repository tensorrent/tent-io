"""Regression tests for intelligence scoring (scoring_version 1.1)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent.parent
if str(_HARNESS) not in sys.path:
    sys.path.insert(0, str(_HARNESS))

from intelligence_scoring_core import build_intelligence_scoring_output


class TestIntelligenceScoringCore(unittest.TestCase):
    def test_default_preset_deterministic_golden_vector(self) -> None:
        """Fixed inputs → fixed scores (guards accidental formula drift)."""
        sweep = {
            "best_profile": {
                "profile": "expand_s1",
                "final_test_acc": 0.8,
                "final_mmlu_test_acc": 0.7,
                "final_conversational_logic_test_acc": 0.6,
                "train_eval_drift": 0.0,
            }
        }
        out = build_intelligence_scoring_output(sweep, scoring_preset="default")
        self.assertEqual(out["scoring_version"], "1.1")
        self.assertEqual(out["scoring_preset"], "default")
        s = out["scores"]
        assert s is not None
        self.assertAlmostEqual(s["logic_chain_score"], 0.71, places=9)
        self.assertAlmostEqual(s["ml_intelligence_score"], 0.725, places=9)
        self.assertAlmostEqual(s["ai_intelligence_score"], 0.44875, places=9)
        self.assertAlmostEqual(s["agi_readiness_score"], 0.5220625, places=9)

    def test_conversation_focused_preset_changes_scores(self) -> None:
        sweep = {
            "best_profile": {
                "profile": "expand_s2",
                "final_test_acc": 0.5,
                "final_mmlu_test_acc": 0.5,
                "final_conversational_logic_test_acc": 0.9,
                "train_eval_drift": 0.0,
            }
        }
        d = build_intelligence_scoring_output(sweep, scoring_preset="default")
        c = build_intelligence_scoring_output(sweep, scoring_preset="conversation_focused")
        self.assertNotEqual(d["scores"]["logic_chain_score"], c["scores"]["logic_chain_score"])

    def test_replay_gap_reduces_replay_consistency(self) -> None:
        sweep = {
            "best_profile": {
                "profile": None,
                "final_test_acc": 1.0,
                "final_mmlu_test_acc": 1.0,
                "final_conversational_logic_test_acc": 1.0,
                "replay_test_acc": 0.0,
                "replay_mmlu_test_acc": 0.0,
                "replay_conversational_logic_test_acc": 0.0,
                "train_eval_drift": 0.0,
            }
        }
        out = build_intelligence_scoring_output(sweep, scoring_preset="default")
        internal = out["components"]["internal"]
        self.assertAlmostEqual(internal["replay_consistency"], 0.0, places=9)

    def test_external_strength_and_alignment_expand_s1(self) -> None:
        sweep = {
            "best_profile": {
                "profile": "expand_s1",
                "final_test_acc": 0.5,
                "final_mmlu_test_acc": 0.5,
                "final_conversational_logic_test_acc": 0.5,
                "train_eval_drift": 0.0,
            }
        }
        external = {
            "favored_profile": "expand_s1",
            "expand_s1": {
                "metrics": {
                    "mmlu_pro_acc": 0.8,
                    "gpqa_acc": 0.8,
                    "long_context_acc": 0.8,
                    "consistency_score": 0.8,
                }
            },
            "expand_s2": {"metrics": {}},
        }
        out = build_intelligence_scoring_output(sweep, external=external, scoring_preset="default")
        ext = out["components"]["external"]
        self.assertEqual(ext["internal_external_alignment"], 1.0)
        self.assertAlmostEqual(ext["external_strength"], 0.8, places=9)

    def test_governance_aligned_ready_boosts_agi(self) -> None:
        sweep = {
            "best_profile": {
                "profile": "expand_s1",
                "final_test_acc": 0.5,
                "final_mmlu_test_acc": 0.5,
                "final_conversational_logic_test_acc": 0.5,
                "train_eval_drift": 0.0,
            }
        }
        decision = {"decision_state": "aligned_ready_for_promotion", "promotion_allowed": True}
        trend = {"contested_ratio_recent": 0.0}
        low = build_intelligence_scoring_output(sweep, decision={}, trend={})
        high = build_intelligence_scoring_output(sweep, decision=decision, trend=trend)
        self.assertGreater(high["scores"]["agi_readiness_score"], low["scores"]["agi_readiness_score"])


if __name__ == "__main__":
    unittest.main()
