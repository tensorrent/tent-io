#!/usr/bin/env bash
# Phase A — Environment snapshot for TENT v4.1 external benchmark validation.
# Edit TENT_IO_ROOT and CORE_BINARY below, then run and save output to env_snapshot.txt:
#   ./env_snapshot.sh > env_snapshot.txt 2>&1

set -e
# --- EDIT THESE FOR YOUR MACHINE ---
TENT_IO_ROOT="${TENT_IO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
CORE_BINARY="${CORE_BINARY:-}"   # e.g. /path/to/tent_core.wasm or /path/to/tent_infer

echo "=== TENT v4.1 External Benchmark — Environment Snapshot ==="
date -u "+%Y-%m-%dT%H:%M:%SZ"
uname -a
if command -v sw_vers &>/dev/null; then
  sw_vers
fi
echo "---"
echo "hw.ncpu: $(sysctl -n hw.ncpu 2>/dev/null || echo 'N/A')"
echo "hw.memsize (bytes): $(sysctl -n hw.memsize 2>/dev/null || echo 'N/A')"
python3 --version
rustc --version 2>/dev/null || echo "rustc: not found"
wasm-pack --version 2>/dev/null || echo "no wasm-pack"
which antigravity 2>/dev/null || echo "antigravity path: [fill in]"
echo "---"
echo "pwd: $(pwd)"
echo "TENT_IO_ROOT: $TENT_IO_ROOT"
if [ -d "$TENT_IO_ROOT/.git" ]; then
  echo "--- git (tent-io) ---"
  git -C "$TENT_IO_ROOT" log -1 --format="%H %ci %s"
  git -C "$TENT_IO_ROOT" diff --stat
else
  echo "Not a git repo: $TENT_IO_ROOT"
fi
echo "---"
echo "--- Core engine file size ---"
if [ -n "$CORE_BINARY" ] && [ -f "$CORE_BINARY" ]; then
  ls -la "$CORE_BINARY"
  shasum -a 256 "$CORE_BINARY"
else
  echo "CORE_BINARY not set or file missing. Set CORE_BINARY=/path/to/tent_core.wasm"
fi
echo "=== End snapshot ==="
