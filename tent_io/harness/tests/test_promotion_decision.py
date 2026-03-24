"""Tests for compute_promotion_decision slot alignment, streak reset, and tie-break."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "compute_promotion_decision.py"


def _run_decision(
    internal: dict,
    external: dict,
    hist_path: Path,
    alignment_runs: int = 2,
    extra: list[str] | None = None,
) -> dict:
    extra = extra or []
    i_path = hist_path.parent / "internal.json"
    e_path = hist_path.parent / "external.json"
    o_path = hist_path.parent / "out.json"
    i_path.write_text(json.dumps(internal), encoding="utf-8")
    e_path.write_text(json.dumps(external), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--internal-summary",
            str(i_path),
            "--external-compare",
            str(e_path),
            "--out",
            str(o_path),
            "--history-out",
            str(hist_path),
            "--alignment-required-runs",
            str(alignment_runs),
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(o_path.read_text(encoding="utf-8"))


class TestPromotionDecision(unittest.TestCase):
    @staticmethod
    def _metrics(val: float) -> dict:
        return {
            "mmlu_pro_acc": val,
            "gpqa_acc": val,
            "long_context_acc": val,
            "consistency_score": val,
        }

    def _external_base(self, favored: str, *, s1: float = 0.7, s2: float = 0.6) -> dict:
        return {
            "favored_profile": favored,
            "winner_votes": {"expand_s1": 3, "expand_s2": 1, "tie_or_missing": 0},
            "expand_s1": {"profile": "expand_s1", "metrics": self._metrics(s1)},
            "expand_s2": {"profile": "expand_s2", "metrics": self._metrics(s2)},
        }

    def test_contested_when_slots_differ(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "hist.ndjson"
            internal = {"best_profile": {"profile": "expand_s2", "margin": 0.1}}
            out = _run_decision(internal, self._external_base("expand_s1"), h)
        self.assertEqual(out["decision_state"], "contested")
        self.assertFalse(out["promotion_allowed"])
        self.assertTrue(out["contested"])
        self.assertFalse(out["aligned"])
        self.assertEqual(out["promotion_blocked_reason"], "internal_external_slot_mismatch")
        self.assertEqual(out["aligned_streak"], 0)

    def test_aligned_when_slots_match_then_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "hist.ndjson"
            internal = {"best_profile": {"profile": "expand_s1", "margin": 0.1}}
            out = _run_decision(internal, self._external_base("expand_s1"), h, alignment_runs=2)
        self.assertFalse(out["contested"])
        self.assertTrue(out["aligned"])
        self.assertEqual(out["decision_state"], "aligned_pending_confirmation")
        self.assertEqual(out["aligned_streak"], 1)

    def test_false_recovery_contested_then_two_aligned(self) -> None:
        """Contested run does not count toward aligned streak."""
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "hist.ndjson"
            ext = self._external_base("expand_s1")
            _run_decision({"best_profile": {"profile": "expand_s2", "margin": 0.1, "train_eval_drift": 0.0}}, ext, h)
            out2 = _run_decision(
                {"best_profile": {"profile": "expand_s1", "margin": 0.1, "train_eval_drift": 0.0}},
                ext,
                h,
                alignment_runs=2,
            )
            self.assertEqual(out2["aligned_streak"], 1)
            out3 = _run_decision(
                {"best_profile": {"profile": "expand_s1", "margin": 0.1, "train_eval_drift": 0.0}},
                ext,
                h,
                alignment_runs=2,
            )
            self.assertEqual(out3["aligned_streak"], 2)
            self.assertEqual(out3["decision_state"], "aligned_ready_for_promotion")
            self.assertTrue(out3["promotion_allowed"])

    def test_insufficient_when_external_tie(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "hist.ndjson"
            ext = self._external_base("expand_s1")
            ext["favored_profile"] = "tie_or_missing"
            out = _run_decision({"best_profile": {"profile": "expand_s1", "margin": 0.1}}, ext, h)
        self.assertEqual(out["decision_state"], "insufficient_signal")

    def test_tie_break_weak_margin_stays_contested(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "hist.ndjson"
            # |s1-s2| ~ 0.01 on mean metrics — confidence stays below default threshold
            ext = self._external_base("expand_s1", s1=0.51, s2=0.50)
            out = _run_decision(
                {"best_profile": {"profile": "expand_s2", "margin": 0.1, "train_eval_drift": 0.0}},
                ext,
                h,
                extra=[
                    "--contested-external-tie-break",
                    "--external-tie-break-streak-required",
                    "3",
                ],
            )
        self.assertEqual(out["decision_state"], "contested")
        self.assertFalse(out["promotion_allowed"])
        self.assertEqual(out.get("tie_break_reason"), "tie_break_confidence_below_effective_threshold")

    def test_mixed_metric_direction_blocks_tie_break(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "hist.ndjson"
            ext = {
                "favored_profile": "expand_s1",
                "winner_votes": {"expand_s1": 3, "expand_s2": 1, "tie_or_missing": 0},
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
                    "metrics": self._metrics(0.50),
                },
            }
            out = _run_decision(
                {"best_profile": {"profile": "expand_s2", "margin": 0.1, "train_eval_drift": 0.0}},
                ext,
                h,
                extra=["--contested-external-tie-break"],
            )
        self.assertEqual(out.get("tie_break_reason"), "low_metric_agreement")
        self.assertEqual(out["decision_state"], "contested")

    def test_tie_break_override_after_streak(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "hist.ndjson"
            ext = self._external_base("expand_s1", s1=0.8, s2=0.5)
            row = {
                "aligned": False,
                "contested": True,
                "external_favored_slot": "expand_s1",
                "external_margin_abs": 0.35,
                "tie_break_momentum": True,
                "external_tie_break_streak": 2,
                "decision_state": "contested",
            }
            h.write_text(json.dumps(row) + "\n", encoding="utf-8")
            out = _run_decision(
                {"best_profile": {"profile": "expand_s2", "margin": 0.1, "train_eval_drift": 0.0}},
                ext,
                h,
                extra=[
                    "--contested-external-tie-break",
                    "--external-tie-break-streak-required",
                    "3",
                ],
            )
        self.assertEqual(out["decision_state"], "contested_external_override")
        self.assertTrue(out["promotion_allowed"])
        self.assertTrue(out.get("tie_break_applied"))
        self.assertGreaterEqual(out.get("tie_break_confidence") or 0, 0.75)

    def test_effective_confidence_can_block_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "hist.ndjson"
            ext = self._external_base("expand_s1", s1=0.8, s2=0.5)
            rows = [
                {
                    "aligned": False,
                    "contested": True,
                    "external_favored_slot": "expand_s1",
                    "external_margin_abs": 0.35,
                    "tie_break_momentum": True,
                    "external_tie_break_streak": 1,
                    "decision_state": "contested",
                    "external_metric_agreement_ratio": 1.0,
                    "tie_break_confidence": 0.74,
                    "tie_break_confidence_threshold_effective": 0.75,
                },
                {
                    "aligned": False,
                    "contested": True,
                    "external_favored_slot": "expand_s1",
                    "external_margin_abs": 0.35,
                    "tie_break_momentum": True,
                    "external_tie_break_streak": 2,
                    "decision_state": "contested",
                    "external_metric_agreement_ratio": 1.0,
                    "tie_break_confidence": 0.76,
                    "tie_break_confidence_threshold_effective": 0.75,
                },
            ]
            h.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            out = _run_decision(
                {"best_profile": {"profile": "expand_s2", "margin": 0.1, "train_eval_drift": 0.0}},
                ext,
                h,
                extra=[
                    "--contested-external-tie-break",
                    "--external-tie-break-streak-required",
                    "3",
                    "--tie-break-use-effective-confidence",
                ],
            )
        self.assertEqual(out["decision_state"], "contested")
        self.assertFalse(out["promotion_allowed"])
        self.assertEqual(out.get("tie_break_metric_used"), "effective_confidence")
        self.assertEqual(
            out.get("tie_break_reason"),
            "tie_break_effective_confidence_below_effective_threshold",
        )

    def test_hysteresis_retains_when_prev_above(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "hist.ndjson"
            ext = self._external_base("expand_s1", s1=0.8, s2=0.5)
            row = {
                "aligned": False,
                "contested": True,
                "external_favored_slot": "expand_s1",
                "external_margin_abs": 0.35,
                "tie_break_momentum": True,
                "external_tie_break_streak": 2,
                "decision_state": "contested_external_override",
                "tie_break_hysteresis_above": True,
                "tie_break_confidence": 0.70,
                "tie_break_confidence_threshold_effective": 0.75,
            }
            h.write_text(json.dumps(row) + "\n", encoding="utf-8")
            out = _run_decision(
                {"best_profile": {"profile": "expand_s2", "margin": 0.1, "train_eval_drift": 0.0}},
                ext,
                h,
                extra=[
                    "--contested-external-tie-break",
                    "--external-tie-break-streak-required",
                    "3",
                    "--tie-break-hysteresis-enable",
                    "--tie-break-hysteresis-high",
                    "0.80",
                    "--tie-break-hysteresis-low",
                    "0.60",
                ],
            )
        self.assertEqual(out["decision_state"], "contested_external_override")
        self.assertTrue(out["promotion_allowed"])
        self.assertTrue(out.get("tie_break_hysteresis_passed"))


if __name__ == "__main__":
    unittest.main()
