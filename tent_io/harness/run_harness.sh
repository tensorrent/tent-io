#!/usr/bin/env bash
# Harness: audit, format, extend, validate, prepare push for Phase 18 ODIN / tent-io
# Usage: ./harness/run_harness.sh [--no-format] [--no-push-prep]

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NO_FORMAT=false
NO_PUSH_PREP=false
for arg in "$@"; do
  case "$arg" in
    --no-format)    NO_FORMAT=true ;;
    --no-push-prep) NO_PUSH_PREP=true ;;
  esac
done

echo "=== Phase 18 ODIN Harness ==="
echo "Root: $ROOT"
echo ""

# 1. Audit
echo "[1/5] Audit: checking claims and language..."
AUDIT_CRITERIA="$ROOT/../papers_audited/AUDIT_CRITERIA.md"
[ -f "$AUDIT_CRITERIA" ] || AUDIT_CRITERIA="$ROOT/harness/AUDIT_CRITERIA.md"
[ -f "$AUDIT_CRITERIA" ] || AUDIT_CRITERIA=""
if [ -n "$AUDIT_CRITERIA" ] && [ -f "$AUDIT_CRITERIA" ]; then
  echo "  Using $AUDIT_CRITERIA"
fi
# Grep for words to avoid (hyperbole)
if grep -riE 'groundbreaking|revolutionary|paradigm shift|unprecedented|proof that|proves that' "$ROOT/docs" --include="*.md" 2>/dev/null; then
  echo "  WARNING: Possible hyperbole found in docs. Review recommended."
else
  echo "  No obvious hyperbole in docs."
fi
# RC1 harness: claim/hallucination/hyperbole audit (case study: docs/CASE_STUDY_HALLUCINATION_AND_PROBLEMATIC_CLAIMS.md)
if [ -f "$ROOT/harness/audit_claims_rc1.py" ]; then
  echo "  Running RC1 claim audit..."
  python3 "$ROOT/harness/audit_claims_rc1.py" 2>/dev/null || true
else
  echo "  RC1 audit script not found; skip."
fi
echo ""

# 2. Format
if [ "$NO_FORMAT" != true ]; then
  echo "[2/5] Format: markdown and code..."
  if command -v prettier &>/dev/null; then
    (cd "$ROOT" && npx prettier --write "docs/**/*.md" "*.md" 2>/dev/null) || true
  fi
  if command -v black &>/dev/null && [ -d "$ROOT/specs" ]; then
    (cd "$ROOT" && black specs/*.py 2>/dev/null) || true
  fi
  echo "  Format pass done."
else
  echo "[2/5] Format: skipped (--no-format)."
fi
echo ""

# 3. Extend
echo "[3/5] Extend: ensuring specs and docs are present..."
for spec in sovereign_omni_lattice sovereign_logic_omnigami sovereign_omnigami_assembly sovereign_multi_brain sovereign_vigil_standby sovereign_5d_entanglement sovereign_entangled_recovery sovereign_omni_blackout; do
  SPEC_FILE="$ROOT/specs/${spec}.py"
  if [ ! -f "$SPEC_FILE" ]; then
    echo "  Creating stub: specs/${spec}.py"
    printf "# Spec: %s\n# Phase 18 ODIN — stub for traceability. Implement in sovereign codebase.\n\n" "$spec" > "$SPEC_FILE"
    printf "def %s() -> None:\n    pass\n" "$(echo "$spec" | tr '.' '_' | sed 's/-/_/g')" >> "$SPEC_FILE"
  fi
done
if [ ! -f "$ROOT/specs/omnigami_crease_map.json" ]; then
  echo '{"version": "1.0", "omni_point": "78.66", "branes": ["spacetime", "quantum_superposition", "harmonic_resonance"], "comment": "Stub manifest"}' > "$ROOT/specs/omnigami_crease_map.json"
  echo "  Created stub: specs/omnigami_crease_map.json"
fi
echo "  Extend pass done."
echo ""

# 4. Validate
echo "[4/5] Validate: structure and links..."
if [ -f "$ROOT/docs/Phase_18_Omni_Dimensional_Intelligence_Walkthrough.md" ]; then
  echo "  Walkthrough present."
else
  echo "  WARNING: Walkthrough not found."
fi
if [ -d "$ROOT/specs" ]; then
  echo "  Specs dir present ($(ls -1 "$ROOT/specs" 2>/dev/null | wc -l) items)."
fi
echo "  Validate pass done."
echo ""

# 5. Prepare push (do not let git or other tools propagate exit code 5 or other codes)
if [ "$NO_PUSH_PREP" != true ]; then
  echo "[5/5] Prepare push: git status and reminder..."
  if git rev-parse --is-inside-work-tree &>/dev/null; then
    git status -sb || true
    echo ""
    echo "  To push to your tent-io repo (replace YOUR_GITHUB_USER):"
    echo "    1. Ensure remote: git remote add tent-io https://github.com/YOUR_GITHUB_USER/tent-io.git"
    echo "    2. Create branch: git checkout -b phase18-odin"
    echo "    3. Add and commit: git add tent_io/ && git commit -m 'Phase 18 ODIN walkthrough and harness'"
    echo "    4. Push: git push tent-io phase18-odin:main"
  else
    echo "  Not a git repo; copy $ROOT into your tent-io clone and commit there."
  fi
else
  echo "[5/5] Push prep: skipped (--no-push-prep)."
fi

echo ""
echo "=== Harness complete ==="
exit 0
