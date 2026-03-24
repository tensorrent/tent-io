"""Unit tests for promotion_decision_logic (no subprocess)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent.parent
if str(_HARNESS) not in sys.path:
    sys.path.insert(0, str(_HARNESS))

from promotion_decision_logic import (  # noqa: E402
    adaptive_effective_threshold,
    agreement_ratio_for_favor,
    alignment_streak_after_run,
    external_tie_break_streak,
    linear_percentile,
    tie_break_confidence,
    tie_break_momentum,
)


class TestPromotionDecisionLogic(unittest.TestCase):
    def test_alignment_streak_resets_after_contested(self) -> None:
        contested_row = '{"aligned": false, "aligned_streak": 0, "decision_state": "contested"}\n'
        out = alignment_streak_after_run([contested_row], aligned=True)
        self.assertEqual(out, 1)

    def test_alignment_streak_increments_when_prior_aligned(self) -> None:
        row = '{"aligned": true, "aligned_streak": 1}\n'
        self.assertEqual(alignment_streak_after_run([row], aligned=True), 2)

    def test_alignment_streak_zero_when_not_aligned(self) -> None:
        row = '{"aligned": true, "aligned_streak": 2}\n'
        self.assertEqual(alignment_streak_after_run([row], aligned=False), 0)

    def test_tie_break_momentum(self) -> None:
        self.assertTrue(tie_break_momentum(True, 0.05, 0.01))
        self.assertFalse(tie_break_momentum(True, 0.005, 0.01))
        self.assertFalse(tie_break_momentum(False, 0.05, 0.01))

    def test_external_tie_break_streak_increments(self) -> None:
        line1 = (
            '{"tie_break_momentum": true, "external_favored_slot": "expand_s1", '
            '"external_margin_abs": 0.05, "external_tie_break_streak": 1}\n'
        )
        st = external_tie_break_streak(
            [line1],
            contested=True,
            enabled=True,
            margin_abs=0.05,
            margin_floor=0.01,
            ext_favored_slot="expand_s1",
        )
        self.assertEqual(st, 2)

    def test_agreement_ratio_mixed_direction(self) -> None:
        ext = {
            "favored_profile": "expand_s1",
            "expand_s1": {
                "profile": "expand_s1",
                "metrics": {
                    "mmlu_pro_acc": 0.53,
                    "gpqa_acc": 0.48,
                    "long_context_acc": 0.51,
                    "consistency_score": 0.49,
                },
            },
            "expand_s2": {
                "profile": "expand_s2",
                "metrics": {
                    "mmlu_pro_acc": 0.50,
                    "gpqa_acc": 0.50,
                    "long_context_acc": 0.50,
                    "consistency_score": 0.50,
                },
            },
        }
        ar = agreement_ratio_for_favor(ext, "expand_s1")
        self.assertEqual(ar, 0.5)

    def test_linear_percentile_six_values(self) -> None:
        xs = [0.6, 0.62, 0.65, 0.7, 0.72, 0.74]
        self.assertAlmostEqual(linear_percentile(xs, 75), 0.715, places=3)

    def test_adaptive_effective_max_of_static_and_clamped_p75(self) -> None:
        hist = [0.6, 0.62, 0.65, 0.7, 0.72, 0.74]
        eff, raw = adaptive_effective_threshold(
            0.65,
            historical_confidences=hist,
            percentile=75.0,
            clamp_min=0.65,
            clamp_max=0.85,
            min_samples=3,
        )
        self.assertAlmostEqual(raw, 0.715, places=3)
        self.assertAlmostEqual(eff, 0.715, places=3)
        self.assertLess(0.71, eff)

    def test_tie_break_confidence_borderline(self) -> None:
        conf, _ = tie_break_confidence(
            margin_abs=0.015,
            tb_streak=1,
            streak_required=3,
            agreement_ratio=1.0,
            best_profile={"train_eval_drift": 0.0},
            relax_drift=False,
            target_margin=0.03,
            drift_tol=1e-6,
        )
        self.assertLess(conf, 0.75)
        conf2, _ = tie_break_confidence(
            margin_abs=0.015,
            tb_streak=3,
            streak_required=3,
            agreement_ratio=1.0,
            best_profile={"train_eval_drift": 0.0},
            relax_drift=False,
            target_margin=0.03,
            drift_tol=1e-6,
        )
        self.assertGreaterEqual(conf2, 0.75)


if __name__ == "__main__":
    unittest.main()
