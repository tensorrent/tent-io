"""Tests for regression delta extraction (mirrors workflow wiring)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(_TOOLS))

from check_intelligence_regression import extract  # noqa: E402


class TestRegressionExtract(unittest.TestCase):
    def test_extract_scores(self) -> None:
        payload = {
            "scores": {
                "ml_intelligence_score": 0.5,
                "logic_chain_score": 0.6,
                "ai_intelligence_score": 0.55,
                "agi_readiness_score": 0.52,
            },
            "components": {"governance": {"contested_ratio_recent": 0.1}},
        }
        got = extract(payload)
        self.assertAlmostEqual(got["ml_intelligence_score"], 0.5)
        self.assertAlmostEqual(got["contested_ratio_recent"], 0.1)


if __name__ == "__main__":
    unittest.main()
