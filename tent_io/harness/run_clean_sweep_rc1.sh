#!/usr/bin/env bash
# Clean sweep RC1: scan entire dev folder + Seagate (if mounted), all text files.
# Optionally run on all local git branches and merge report.
#
# Usage:
#   ./harness/run_clean_sweep_rc1.sh              # dev + Seagate, all-text, current branch
#   ./harness/run_clean_sweep_rc1.sh --all-branches  # run on each branch, append to report (slow)
#
# Output: tent_io/harness/reports/CLEAN_SWEEP_RC1_FINDINGS.md (and .json)

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Dev repo root (parent of tent_io)
DEV_ROOT="$(cd "$ROOT/.." && pwd)"
REPORTS="$ROOT/harness/reports"
OUT_MD="$REPORTS/CLEAN_SWEEP_RC1_FINDINGS.md"
OUT_JSON="$REPORTS/CLEAN_SWEEP_RC1_FINDINGS.json"
AUDIT_SCRIPT="$ROOT/harness/audit_claims_rc1.py"

ALL_BRANCHES=false
for arg in "$@"; do
  case "$arg" in
    --all-branches) ALL_BRANCHES=true ;;
  esac
done

mkdir -p "$REPORTS"
cd "$DEV_ROOT"

run_audit() {
  python3 "$AUDIT_SCRIPT" --dev --seagate --all-text --out "$1" 2>/dev/null || true
  python3 "$AUDIT_SCRIPT" --dev --seagate --all-text --json > "$2" 2>/dev/null || true
}

echo "=== RC1 Clean sweep ==="
echo "Dev root: $DEV_ROOT"
echo "Seagate:  $([ -d '/Volumes/Seagate 4tb' ] && echo 'mounted' || echo 'not mounted')"
echo ""

if [ "$ALL_BRANCHES" = true ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[Clean sweep] Running on all local branches..."
  SAVED_BRANCH=""
  if git symbolic-ref -q HEAD >/dev/null; then
    SAVED_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  fi
  echo "Branch,Findings" > "$REPORTS/CLEAN_SWEEP_BRANCHES.csv"
  for branch in $(git branch -l | sed 's/^[* ]*//'); do
    git checkout -q "$branch" 2>/dev/null || continue
    count=$(python3 "$AUDIT_SCRIPT" --dev --seagate --all-text --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('count',0))" 2>/dev/null || echo "0")
    echo "$branch,$count" >> "$REPORTS/CLEAN_SWEEP_BRANCHES.csv"
  done
  [ -n "$SAVED_BRANCH" ] && git checkout -q "$SAVED_BRANCH" 2>/dev/null || true
  echo "Per-branch counts: $REPORTS/CLEAN_SWEEP_BRANCHES.csv"
fi

echo "[Clean sweep] Full audit (dev + Seagate, all-text)..."
run_audit "$OUT_MD" "$OUT_JSON"

echo ""
echo "Report (MD):  $OUT_MD"
echo "Report (JSON): $OUT_JSON"
echo "=== Clean sweep done ==="
