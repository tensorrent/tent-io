#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/Users/coo-koba42/dev/tensorrent_tent_io_publish"
VENV_PY="$REPO_ROOT/.venv-airllm/bin/python"
CLI="$REPO_ROOT/tent_io/harness/bin/airllm_sparseplug_cli.py"

exec "$VENV_PY" "$CLI" "$@"
