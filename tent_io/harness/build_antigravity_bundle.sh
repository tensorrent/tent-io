#!/usr/bin/env bash
# Run the local Antigravity/TENT build pipeline and write a compact status summary.
#
# Outputs:
# - harness/reports/omni_solo_spec_sheet.json
# - harness/reports/odin_real_benchmark_atomic.ndjson
# - harness/reports/odin_real_benchmark_spec_sheet.json
# - harness/tent_v41_external_benchmark/{tent_eval_*,env_snapshot.txt,HASH_MANIFEST.sha256}
# - harness/reports/antigravity_build_status.json

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HARNESS_DIR="$ROOT/harness"
T41_DIR="$HARNESS_DIR/tent_v41_external_benchmark"
REPORTS_DIR="$HARNESS_DIR/reports"
STATUS_FILE="$REPORTS_DIR/antigravity_build_status.json"

mkdir -p "$REPORTS_DIR"

run_step() {
  local name="$1"
  shift
  if "$@"; then
    echo "OK   $name"
    return 0
  fi
  echo "FAIL $name"
  return 1
}

iso_now() {
  date -u "+%Y-%m-%dT%H:%M:%SZ"
}

ts_start="$(iso_now)"

rc_omni=1
rc_odin=1
rc_t41=1
rc_env=1
rc_hash=1

run_step "omni_solo" python3 "$HARNESS_DIR/omni_benchmark_solo.py" --json
rc_omni=$?

run_step "odin_real_benchmark" python3 "$HARNESS_DIR/odin_real_benchmark.py"
rc_odin=$?

run_step "tent_v41_adapter" python3 "$T41_DIR/tent_benchmark_adapter.py"
rc_t41=$?

run_step "tent_v41_env_snapshot" bash -lc "cd \"$T41_DIR\" && ./env_snapshot.sh > env_snapshot.txt 2>&1"
rc_env=$?

run_step "tent_v41_hash_manifest" bash -lc "cd \"$T41_DIR\" && ./generate_hash_manifest.sh"
rc_hash=$?

ts_end="$(iso_now)"

overall="PASS"
if [ "$rc_omni" -ne 0 ] || [ "$rc_odin" -ne 0 ] || [ "$rc_t41" -ne 0 ] || [ "$rc_env" -ne 0 ] || [ "$rc_hash" -ne 0 ]; then
  overall="PARTIAL"
fi

cat > "$STATUS_FILE" <<EOF
{
  "started_at_utc": "$ts_start",
  "ended_at_utc": "$ts_end",
  "overall": "$overall",
  "steps": {
    "omni_solo": $rc_omni,
    "odin_real_benchmark": $rc_odin,
    "tent_v41_adapter": $rc_t41,
    "tent_v41_env_snapshot": $rc_env,
    "tent_v41_hash_manifest": $rc_hash
  },
  "notes": [
    "A non-zero ODIN or TENT adapter step commonly indicates inference engine is not configured.",
    "Set ANTIGRAVITY_INFERENCE_URL or ANTIGRAVITY_BIN for ODIN real answers.",
    "Set TENT inference variables in tent_benchmark_adapter.py for non-stub execution."
  ]
}
EOF

echo "Wrote status: $STATUS_FILE"
[ "$overall" = "PASS" ] && exit 0
exit 1
