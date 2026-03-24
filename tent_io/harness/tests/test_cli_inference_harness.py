"""Tests for shared CLI binary resolution and subprocess contract."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent.parent
if str(_HARNESS) not in sys.path:
    sys.path.insert(0, str(_HARNESS))

from cli_inference_harness import CLI_BIN_ENV_KEYS, resolve_cli_binary_from_env, run_cli_inference


class TestCliInferenceHarness(unittest.TestCase):
    def test_resolve_prefers_first_existing_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "infer.sh"
            p.write_text('#!/bin/sh\necho ok\n', encoding="utf-8")
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
            env = {k: "" for k in CLI_BIN_ENV_KEYS}
            env["TENT_INFERENCE_BIN"] = str(p)
            env["HARNESS_CLI_BIN"] = str(p)
            self.assertEqual(resolve_cli_binary_from_env(env), str(p.resolve()))

    def test_resolve_skips_missing_file(self) -> None:
        env = {"HARNESS_CLI_BIN": "/nonexistent/path/to/binary"}
        self.assertIsNone(resolve_cli_binary_from_env(env))

    def test_run_cli_inference_echo_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            script = tmp_path / "echo_infer.py"
            script.write_text(
                """#!/usr/bin/env python3
import sys
prompt = ""
i = 0
while i < len(sys.argv):
    if sys.argv[i] == "--prompt" and i + 1 < len(sys.argv):
        prompt = sys.argv[i + 1]
    i += 1
print(prompt, end="")
""",
                encoding="utf-8",
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            for k in CLI_BIN_ENV_KEYS:
                env.pop(k, None)
            env["HARNESS_CLI_BIN"] = str(script)
            old = os.environ
            try:
                os.environ.clear()
                os.environ.update(env)
                out = run_cli_inference("hello", "q1", cwd=tmp_path, timeout=5)
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(out, "hello")

    def test_run_returns_empty_when_no_binary(self) -> None:
        env = os.environ.copy()
        for k in CLI_BIN_ENV_KEYS:
            env.pop(k, None)
        old = os.environ
        try:
            os.environ.clear()
            os.environ.update(env)
            out = run_cli_inference("x", "y", cwd=Path("."))
        finally:
            os.environ.clear()
            os.environ.update(old)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
