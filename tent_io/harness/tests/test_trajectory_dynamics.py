"""Unit tests for ``trajectory_dynamics.py``."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent.parent


class TestTrajectoryDynamics(unittest.TestCase):
    def test_large_swing_instability(self) -> None:
        sys.path.insert(0, str(_HARNESS))
        import trajectory_dynamics as td  # noqa: PLC0415

        traj = [
            {"confidence_distance_to_threshold": 0.35},
            {"confidence_distance_to_threshold": -0.35},
            {"confidence_distance_to_threshold": 0.3},
        ]
        self.assertEqual(
            td.classify_trajectory_basin(traj, boundary_crossings=[], oscillation_amplitude_band=0.2),
            "large_swing_instability",
        )

    def test_approach_vector_alignment(self) -> None:
        sys.path.insert(0, str(_HARNESS))
        import trajectory_dynamics as td  # noqa: PLC0415

        base = td.augment_trajectory_dynamics(
            [
                {
                    "external_margin_abs": 0.01,
                    "external_metric_agreement_ratio": 0.7,
                    "external_tie_break_streak": 2,
                    "confidence_distance_to_threshold": -0.1,
                    "tie_break_reason": "x",
                },
                {
                    "external_margin_abs": 0.02,
                    "external_metric_agreement_ratio": 0.75,
                    "external_tie_break_streak": 3,
                    "confidence_distance_to_threshold": -0.05,
                    "tie_break_reason": "x",
                },
            ],
            near_boundary_epsilon=0.05,
        )
        out = td.add_approach_vectors(base)
        self.assertEqual(len(out[1]["approach_delta_mas"]), 3)
        self.assertIsNotNone(out[1]["alignment_with_promotion_direction"])


if __name__ == "__main__":
    unittest.main()
