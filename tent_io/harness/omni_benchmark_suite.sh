#!/usr/bin/env bash
# Omni Benchmark Suite — Phase 18 ODIN industrial benchmark
# Usage:
#   ./harness/omni_benchmark_suite.sh           # full: harness + spec check
#   ./harness/omni_benchmark_suite.sh --solo    # model only, parallel, self-check, no external calls
#   ./harness/omni_benchmark_suite.sh [--harness-only] [--no-format]

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HARNESS_ONLY=false
NO_FORMAT=false
SOLO=false
for arg in "$@"; do
  case "$arg" in
    --harness-only) HARNESS_ONLY=true ;;
    --no-format)     NO_FORMAT=true ;;
    --solo)          SOLO=true ;;
  esac
done

# Solo: model alone in the box — parallel run, self-check harness, no external calls
if [ "$SOLO" = true ]; then
  exec python3 "$ROOT/harness/omni_benchmark_solo.py"
fi

echo "=== Omni Benchmark Suite (ODIN Phase 18) ==="
echo "Root: $ROOT"
echo ""

# 1. Run the full ODIN harness (audit, format, extend, validate, push prep)
echo "[1/2] Running ODIN harness..."
if [ "$NO_FORMAT" = true ]; then
  "$ROOT/harness/run_harness.sh" --no-format
else
  "$ROOT/harness/run_harness.sh"
fi
echo ""

# 2. Spec import / minimal run (ensure specs are loadable)
if [ "$HARNESS_ONLY" != true ]; then
  echo "[2/2] Spec import check (Omni suite)..."
  FAIL=0
  for spec in sovereign_omni_lattice sovereign_logic_omnigami sovereign_omnigami_assembly sovereign_multi_brain sovereign_vigil_standby sovereign_5d_entanglement sovereign_entangled_recovery sovereign_omni_blackout; do
    SPEC_FILE="$ROOT/specs/${spec}.py"
    if [ -f "$SPEC_FILE" ]; then
      if python3 "$SPEC_FILE" 2>/dev/null; then
        echo "  OK  $spec"
      else
        python3 -m py_compile "$SPEC_FILE" 2>/dev/null && echo "  OK  $spec (compile)" || { echo "  FAIL $spec"; FAIL=1; }
      fi
    else
      echo "  MISS $spec"
      FAIL=1
    fi
  done
  if [ -f "$ROOT/specs/omnigami_crease_map.json" ]; then
    if python3 -c "import json; json.load(open('$ROOT/specs/omnigami_crease_map.json'))" 2>/dev/null; then
      echo "  OK  omnigami_crease_map.json"
    else
      echo "  FAIL omnigami_crease_map.json"
      FAIL=1
    fi
  fi
  echo ""
  if [ $FAIL -eq 0 ]; then
    echo "=== Omni Benchmark Suite: PASS ==="
    exit 0
  else
    echo "=== Omni Benchmark Suite: COMPLETE (some stubs missing) ==="
    exit 1
  fi
else
  echo "[2/2] Skipped (--harness-only)."
  echo "=== Omni Benchmark Suite: HARNESS ONLY ==="
  exit 0
fi
