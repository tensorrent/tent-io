"""
Single CLI inference harness for ODIN, TENT v4.1 adapter, and related tools.

Contract (one subprocess shape for every caller):
  <binary> --prompt "<text>" --question-id "<id>"

Environment (first existing file path wins):
  HARNESS_CLI_BIN  — preferred canonical name
  INFERENCE_BIN
  ANTIGRAVITY_BIN  — legacy (ODIN docs)
  TENT_INFERENCE_BIN — legacy (TENT v4.1 docs)

Binaries that only need the prompt may ignore ``--question-id``; it is always passed for a stable interface.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

CLI_BIN_ENV_KEYS: tuple[str, ...] = (
    "HARNESS_CLI_BIN",
    "INFERENCE_BIN",
    "ANTIGRAVITY_BIN",
    "TENT_INFERENCE_BIN",
)


def resolve_cli_binary_from_env(env: Mapping[str, str] | None = None) -> str | None:
    """Resolve CLI binary using the same key order as :func:`resolve_cli_binary`."""
    src = env if env is not None else os.environ
    for key in CLI_BIN_ENV_KEYS:
        raw = (src.get(key) or "").strip()
        if not raw:
            continue
        p = Path(raw)
        if p.is_file():
            return str(p.resolve())
    return None


def resolve_cli_binary() -> str | None:
    """Return absolute path to the first configured CLI binary that exists on disk."""
    return resolve_cli_binary_from_env(os.environ)


def cli_binary_configured() -> bool:
    return resolve_cli_binary() is not None


def run_cli_inference(prompt: str, question_id: str, *, cwd: Path, timeout: int = 120) -> str:
    """
    Run the resolved CLI binary; stdout is the model answer.

    Returns empty string if no binary is resolved (callers may map to stub).
    On subprocess failure, returns a line starting with ``[ERROR ...]``.
    """
    bin_path = resolve_cli_binary()
    if not bin_path:
        return ""
    r = subprocess.run(
        [bin_path, "--prompt", prompt, "--question-id", question_id],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd),
    )
    if r.returncode != 0:
        return f"[ERROR exit {r.returncode}] {r.stderr or r.stdout or ''}"
    return (r.stdout or "").strip()


def cli_binary_resolution_hint() -> str:
    """Human-readable list of env vars for error messages."""
    return " or ".join(CLI_BIN_ENV_KEYS)
