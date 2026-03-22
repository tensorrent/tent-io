#!/usr/bin/env bash
# Phase D.2 — Generate SHA-256 manifest of deliverable files for TENT v4.1 validation.
# Run from this directory after env_snapshot, fetch, and adapter have produced their outputs.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

OUTPUT="HASH_MANIFEST.sha256"
FILES=(
  env_snapshot.txt
  benchmark_questions_100.json
  benchmark_questions_gpqa_100.json
  tent_eval_atomic_logs.json
  tent_eval_summary.json
  tent_eval_transcript.txt
  network_capture_during_eval.pcap
  network_during.txt
)

echo "# TENT v4.1 External Benchmark — SHA-256 manifest" > "$OUTPUT"
echo "# Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')" >> "$OUTPUT"
echo "" >> "$OUTPUT"

for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    shasum -a 256 "$f" >> "$OUTPUT"
  else
    echo "# (missing) $f" >> "$OUTPUT"
  fi
done

echo "Wrote $OUTPUT"
cat "$OUTPUT"
