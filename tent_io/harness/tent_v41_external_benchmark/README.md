# TENT v4.1 External Benchmark Validation — Deliverable Bundle

**Purpose:** Prove TENT v4.1 (Rust/WASM) on real, unseen benchmark questions with every answer logged and verifiable.

**No external model calls.** Inference is local only (TENT/Antigravity engine). The adapter never calls out to any external API or cloud model — that’s the point. Proof of network isolation (e.g. tcpdump) confirms it.

**Full requirements:** `docs/TENT_V41_EXTERNAL_BENCHMARK_VALIDATION.md` (in dev repo).

---

## What this folder contains

| File | Phase | Description |
|------|--------|-------------|
| `README.md` | — | This file; how to verify |
| `env_snapshot.sh` | A | Capture hardware/software env → `env_snapshot.txt` |
| `fetch_mmlu_pro_100.py` | B | Pull 100 MMLU-Pro questions from HuggingFace → `benchmark_questions_100.json` |
| `fetch_gpqa_100.py` | B | Pull 100 GPQA Diamond questions → `benchmark_questions_gpqa_100.json` |
| `tent_benchmark_adapter.py` | C | Run inference, grade, log atomic JSON + summary + transcript |
| `generate_hash_manifest.sh` | D | SHA-256 of all deliverables → `HASH_MANIFEST.sha256` |
| `benchmark_questions_10_builtin.json` | B (Option 3) | 3 built-in questions if you skip HuggingFace fetch |

---

## Final deliverable bundle (after running all phases)

```
tent_v41_external_benchmark/
├── README.md
├── HASH_MANIFEST.sha256
├── env_snapshot.txt
├── benchmark_questions_100.json
├── tent_eval_atomic_logs.json
├── tent_eval_summary.json
├── tent_eval_transcript.txt
├── network_capture_during_eval.pcap   # or network_during.txt
├── tent_benchmark_adapter.py
├── fetch_mmlu_pro_100.py
├── fetch_gpqa_100.py
├── env_snapshot.sh
└── generate_hash_manifest.sh
```

---

## Quick start (when home with Antigravity)

1. **Set TENT inference pattern** (one of):
   - `TENT_INFERENCE_PATTERN=cli` and `TENT_INFERENCE_BIN=/path/to/tent_infer`
   - `TENT_INFERENCE_PATTERN=http` and `TENT_INFERENCE_URL=http://localhost:PORT/infer`
   - `TENT_INFERENCE_PATTERN=stub` (no engine; for pipeline test only)

2. **Phase A:** `./env_snapshot.sh` → edit paths inside for your repo and binary.

3. **Phase B:** `python3 fetch_mmlu_pro_100.py` (requires `pip install datasets`).

4. **Phase C:** `python3 tent_benchmark_adapter.py` (reads `benchmark_questions_100.json`, writes atomic logs + summary + transcript).

5. **Phase D:** `./generate_hash_manifest.sh`.

6. **Network proof:** Run `tcpdump` or `lsof -i` during step 4; see comments in adapter.

---

## Verifying the proof

- **Accuracy:** Open `tent_eval_atomic_logs.json`; each object has `prompt_sent_to_tent`, `tent_raw_output`, `expected_answer`, `is_correct`.
- **Footprint:** See `env_snapshot.txt` for `ls -la` and `shasum` of the core binary.
- **No network:** Inspect `network_capture_during_eval.pcap` or diff of `lsof -i` before/during run.
