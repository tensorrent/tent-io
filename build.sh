#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# build.sh — TENT v9.0 + BRA Kernel  |  One-shot compile → test → report
# Author: Brad Wallace
# Usage:  bash build.sh
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/src"
BIN="$ROOT/bin"
TESTS="$ROOT/tests"

BLD="\033[1m"
GRN="\033[92m"
RED="\033[91m"
CYN="\033[96m"
RST="\033[0m"

step() { echo -e "\n${BLD}${CYN}── $1${RST}"; }
pass() { echo -e "  ${GRN}✓${RST}  $1"; }
die()  { echo -e "  ${RED}✗  $1${RST}" >&2; exit 1; }

echo -e "\n${BLD}${CYN}╔══════════════════════════════════════════════════════════════╗${RST}"
echo -e "${BLD}${CYN}║  TENT v9.0 + BRA Kernel — Final Build                        ║${RST}"
echo -e "${BLD}${CYN}╚══════════════════════════════════════════════════════════════╝${RST}"

# ── 0. Prerequisites ──────────────────────────────────────────────────────────
step "0. Checking prerequisites"
command -v rustc  >/dev/null 2>&1 || die "rustc not found. Install: apt install rustc"
command -v python3>/dev/null 2>&1 || die "python3 not found"
RUSTC_VER=$(rustc --version | awk '{print $2}')
PY_VER=$(python3 --version | awk '{print $2}')
pass "rustc $RUSTC_VER"
pass "python3 $PY_VER"

# ── 1. Compile BRA Rust kernel → shared library ───────────────────────────────
step "1. Compiling BRA Rust kernel → libbra.so"
mkdir -p "$BIN"
START=$(date +%s%3N)
rustc --edition 2021 \
      -C opt-level=3 \
      -C codegen-units=1 \
      --crate-type cdylib \
      -o "$BIN/libbra.so" \
      "$SRC/bra_kernel.rs" 2>&1
strip "$BIN/libbra.so"
END=$(date +%s%3N)
ELAPSED=$(( END - START ))
SO_SIZE=$(du -h "$BIN/libbra.so" | cut -f1)
SYMBOLS=$(nm -D "$BIN/libbra.so" | grep -c " T bra_")
pass "libbra.so  $SO_SIZE  $SYMBOLS exported symbols  (${ELAPSED}ms)"

# ── 2. Verify BRA exports ─────────────────────────────────────────────────────
step "2. Verifying exported symbols"
for sym in bra_render bra_energy bra_mag bra_verify bra_word_charge; do
    nm -D "$BIN/libbra.so" | grep -q " T $sym" || die "Missing symbol: $sym"
    pass "$sym"
done

# ── 3. Run integrated test suite ──────────────────────────────────────────────
step "3. Running integrated test suite (Phase 1 + 2 + 3)"
cd "$TESTS"
python3 run_tests.py
TEST_EXIT=$?
cd "$ROOT"

# ── 4. Build summary ──────────────────────────────────────────────────────────
echo -e "\n${BLD}${CYN}════════════════════════════════════════════════════════════════${RST}"
echo -e "${BLD}${CYN}  BUILD COMPLETE${RST}"
echo -e "${BLD}${CYN}════════════════════════════════════════════════════════════════${RST}"
echo -e "  Kernel  : $BIN/libbra.so  ($SO_SIZE stripped)"
echo -e "  Engine  : $SRC/tent_v9.py"
echo -e "  Bridge  : $SRC/bra_bridge.py"
echo -e "  Tests   : $TESTS/run_tests.py"
if [ $TEST_EXIT -eq 0 ]; then
    echo -e "  Status  : ${GRN}${BLD}PRODUCTION READY${RST}"
else
    echo -e "  Status  : ${RED}${BLD}TESTS FAILED${RST}"
    exit 1
fi
echo -e "${BLD}${CYN}════════════════════════════════════════════════════════════════${RST}\n"
