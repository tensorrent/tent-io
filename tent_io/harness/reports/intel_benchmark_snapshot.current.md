# Intelligence benchmark snapshot

## Internal harness (from artifacts if present)

- best_profile: `None`
- rank_by: `None`
- metrics: `{}`
- intelligence_scores: `{}`

## Lanes

### odin
- `{"lane": "odin_mmlu_pro_sample", "script": "/Users/coo-koba42/dev/tensorrent_tent_io_publish/tent_io/harness/odin_real_benchmark.py", "questions_default": "/Users/coo-koba42/dev/tensorrent_tent_io_publish/tent_io/harness/fixtures/mmlu_pro_sample.json", "inference_mode": "cli", "returncode": 0, "passed": 3, "total": 3, "accuracy_0_1": 1.0, "note": "Stub inference returns empty answers unless ANTIGRAVITY_INFERENCE_URL is set or a CLI binary is resolved (HARNESS_CLI_BIN / INFERENCE_BIN / ANTIGRAVITY_BIN / TENT_INFERENCE_BIN).", "ndjson_out": "/Users/coo-koba42/dev/tensorrent_tent_io_publish/tent_io/harness/reports/intel_snapshot_odin.ndjson"}`

### gsm8k_heuristic
- `{"rows": 0, "accuracy": 0.0, "note": "Heuristic solver baseline from eval_gsm8k_solver.py; not the LLT model unless wired.", "lane": "gsm8k_heuristic_baseline", "script": "/Users/coo-koba42/dev/tensorrent_tent_io_publish/tent_io/harness/training/eval_gsm8k_solver.py", "returncode": 0}`

### tent_v41
- `{"lane": "tent_v41_external_builtin_cli", "inference_mode": "cli", "tent_inference_pattern": "cli", "tent_inference_bin_configured": true, "returncode": 0, "summary_path": "/Users/coo-koba42/dev/tensorrent_tent_io_publish/tent_io/harness/reports/intel_snapshot_tent_v41_summary.json", "summary": {"benchmark": "TENT v4.1 validation (built-in)", "source": "builtin (Option 3 \u2014 minimum viable)", "model": "TENT v4.1", "total_questions": 3, "correct": 3, "incorrect": 0, "accuracy_percent": 100.0, "average_inference_ms": 2391.1875, "total_runtime_seconds": 7.17, "core_footprint_bytes": null, "network_isolation": "(not captured)", "category_breakdown": {"computer_science": {"total": 1, "correct": 1, "accuracy": 100.0}, "chemistry": {"total": 1, "correct": 1, "accuracy": 100.0}, "physics": {"to`

## Interpretation

- Internal metrics are from the in-repo LLT expansion pipeline (as reported).
- ODIN / TENT v4.1 stub lanes validate wiring; accuracy is not a frontier comparison unless a real inference backend is configured.
- GSM8K row reports a heuristic baseline unless a model-backed solver is integrated.

Full JSON: `/Users/coo-koba42/dev/tensorrent_tent_io_publish/tent_io/harness/reports/intel_benchmark_snapshot.current.json`
