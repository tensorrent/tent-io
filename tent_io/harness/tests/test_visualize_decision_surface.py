"""Tests for synthetic tie-break decision surface (``visualize_decision_surface.py``)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent.parent
_TOOLS = _HARNESS / "tools"
_SCRIPT = _TOOLS / "visualize_decision_surface.py"


class TestVisualizeDecisionSurface(unittest.TestCase):
    def test_evaluate_tie_break_cell_override_and_gate(self) -> None:
        sys.path.insert(0, str(_TOOLS))
        import visualize_decision_surface as vds  # noqa: PLC0415

        cell = vds.evaluate_tie_break_cell(
            margin_abs=0.03,
            agreement_ratio=0.8,
            tb_streak=3,
            favored="expand_s1",
            agreement_floor=0.6,
            margin_floor=0.01,
            effective_threshold=0.75,
            streak_required=3,
            target_margin=0.03,
            best_profile={},
            relax_drift=True,
            drift_tol=1e-6,
        )
        self.assertEqual(cell["decision_state"], "contested_external_override")
        self.assertTrue(cell["promotion_allowed"])
        self.assertIsNotNone(cell["tie_break_confidence"])

        blocked = vds.evaluate_tie_break_cell(
            margin_abs=0.03,
            agreement_ratio=0.5,
            tb_streak=3,
            favored="expand_s1",
            agreement_floor=0.6,
            margin_floor=0.01,
            effective_threshold=0.75,
            streak_required=3,
            target_margin=0.03,
            best_profile={},
            relax_drift=True,
            drift_tol=1e-6,
        )
        self.assertEqual(blocked["tie_break_reason"], "low_metric_agreement")
        self.assertIsNone(blocked["tie_break_confidence"])

    def test_augment_trajectory_dynamics_velocity_and_dwell(self) -> None:
        sys.path.insert(0, str(_HARNESS))
        import trajectory_dynamics as td  # noqa: PLC0415

        base = [
            {
                "confidence_distance_to_threshold": -0.08,
                "tie_break_reason": "tie_break_confidence_below_effective_threshold",
            },
            {
                "confidence_distance_to_threshold": -0.03,
                "tie_break_reason": "tie_break_confidence_below_effective_threshold",
            },
            {
                "confidence_distance_to_threshold": 0.02,
                "tie_break_reason": "tie_break_confidence_threshold_met",
            },
        ]
        aug = td.augment_trajectory_dynamics(base, near_boundary_epsilon=0.05)
        self.assertEqual(aug[0]["confidence_velocity"], None)
        self.assertAlmostEqual(aug[1]["confidence_velocity"], 0.05)
        self.assertAlmostEqual(aug[1]["normalized_confidence_velocity"], 0.05 / (0.08 + td.EPS_VEL))
        self.assertAlmostEqual(aug[2]["confidence_velocity"], 0.05)
        self.assertAlmostEqual(aug[2]["confidence_acceleration"], 0.0)
        self.assertEqual(aug[0]["near_boundary_streak"], 0)
        self.assertEqual(aug[1]["near_boundary_streak"], 1)
        self.assertEqual(aug[2]["near_boundary_streak"], 2)
        self.assertEqual(aug[1]["trajectory_blocking_reason"], "tie_break_confidence_below_effective_threshold")

    def test_classify_basin_stuck_and_converging(self) -> None:
        sys.path.insert(0, str(_HARNESS))
        import trajectory_dynamics as td  # noqa: PLC0415

        stuck = [
            {"confidence_distance_to_threshold": -0.2},
            {"confidence_distance_to_threshold": -0.15},
        ]
        self.assertEqual(
            td.classify_trajectory_basin(stuck, boundary_crossings=[]),
            "stuck_low_signal",
        )
        conv = [
            {"confidence_distance_to_threshold": -0.12},
            {"confidence_distance_to_threshold": -0.05},
        ]
        self.assertEqual(
            td.classify_trajectory_basin(conv, boundary_crossings=[]),
            "converging_to_promotion",
        )

    def test_boundary_crossings_from_trajectory(self) -> None:
        sys.path.insert(0, str(_HARNESS))
        import trajectory_dynamics as td  # noqa: PLC0415

        seq = [
            {
                "tie_break_confidence": 0.7,
                "effective_threshold_used": 0.75,
                "trajectory_index": 0,
                "file_line_index": 0,
                "timestamp_utc": "t0",
            },
            {
                "tie_break_confidence": 0.78,
                "effective_threshold_used": 0.75,
                "trajectory_index": 1,
                "file_line_index": 1,
                "timestamp_utc": "t1",
            },
        ]
        crosses = td.boundary_crossings_from_trajectory(seq)
        self.assertEqual(len(crosses), 1)
        self.assertEqual(crosses[0]["direction"], "up")

    def test_cli_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outp = Path(td) / "surface.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(_SCRIPT),
                    "--output",
                    str(outp),
                    "--margin-steps",
                    "4",
                    "--agreement-steps",
                    "4",
                    "--streak-max",
                    "1",
                    "--streak-required",
                    "3",
                    "--include-aligned-slice",
                ],
                cwd=str(_HARNESS.parent),
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
            data = json.loads(outp.read_text(encoding="utf-8"))
            self.assertIn("contested_tie_break_grid", data)
            self.assertIn("aligned_path_grid", data)
            self.assertEqual(data["meta"]["tie_break_confidence_threshold_effective"], 0.75)
            self.assertIn("tie_break_blocking_reason_slice", data)
            self.assertIn("tie_break_boundary_crossings", data)
            self.assertIn("history_trajectory_contested", data)

    def test_cli_history_trajectory_and_crossing(self) -> None:
        row_a = {
            "decision_state": "contested",
            "external_margin_abs": 0.02,
            "external_metric_agreement_ratio": 0.8,
            "external_tie_break_streak": 3,
            "tie_break_confidence": 0.7,
            "tie_break_confidence_threshold_effective": 0.75,
            "tie_break_reason": "tie_break_confidence_below_effective_threshold",
        }
        row_b = {
            "decision_state": "contested",
            "external_margin_abs": 0.021,
            "external_metric_agreement_ratio": 0.81,
            "external_tie_break_streak": 3,
            "tie_break_confidence": 0.78,
            "tie_break_confidence_threshold_effective": 0.75,
            "tie_break_reason": "tie_break_confidence_threshold_met",
        }
        with tempfile.TemporaryDirectory() as td:
            hist = Path(td) / "hist.ndjson"
            hist.write_text(json.dumps(row_a) + "\n" + json.dumps(row_b) + "\n", encoding="utf-8")
            outp = Path(td) / "surface.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(_SCRIPT),
                    "--output",
                    str(outp),
                    "--history",
                    str(hist),
                    "--margin-steps",
                    "5",
                    "--agreement-steps",
                    "5",
                    "--streak-max",
                    "3",
                    "--png-streak",
                    "3",
                ],
                cwd=str(_HARNESS.parent),
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
            data = json.loads(outp.read_text(encoding="utf-8"))
            self.assertEqual(len(data["history_trajectory_contested"]), 2)
            self.assertEqual(len(data["tie_break_boundary_crossings"]), 1)
            self.assertIsNotNone(data["history_trajectory_contested"][0]["confidence_distance_to_threshold"])
            self.assertIn("confidence_velocity", data["history_trajectory_contested"][1])
            self.assertIn("trajectory_dynamics_summary", data["meta"])
            self.assertIn("stability_score", data["meta"]["trajectory_dynamics_summary"])
            self.assertEqual(
                data["history_trajectory_contested"][1]["trajectory_blocking_reason"],
                data["history_trajectory_contested"][1]["tie_break_reason"],
            )


if __name__ == "__main__":
    unittest.main()
