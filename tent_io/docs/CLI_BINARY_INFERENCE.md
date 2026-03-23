# CLI binary inference (one harness)

All benchmark lanes that call a **local executable** use **`tent_io/harness/cli_inference_harness.py`**: one subprocess shape and one resolution order for env vars.

## Subprocess contract

```text
<binary> --prompt "<full prompt text>" --question-id "<question id>"
```

- **Stdout:** model answer (letter or text; each lane’s grader defines extraction).
- **Exit non-zero:** treated as error; stderr/stdout may be surfaced in logs.

Engines that only need the prompt may **ignore** `--question-id`; it is always passed so ODIN and TENT v4.1 share the same interface.

## Environment (first existing file wins)

| Variable | Role |
|----------|------|
| `HARNESS_CLI_BIN` | Preferred name for new setups |
| `INFERENCE_BIN` | Generic alias |
| `ANTIGRAVITY_BIN` | Legacy (ODIN docs / older scripts) |
| `TENT_INFERENCE_BIN` | Legacy (TENT v4.1 docs) |

Only **one** path should be needed for both ODIN and TENT v4.1 when both use CLI.

## Lanes

### ODIN (`odin_real_benchmark.py`)

- **HTTP** still takes precedence: if `ANTIGRAVITY_INFERENCE_URL` is set, it is used instead of CLI.
- Otherwise the shared harness resolves a binary and runs the contract above with `cwd` = `tent_io` (directory containing `harness/`).

```bash
export HARNESS_CLI_BIN="/absolute/path/to/infer"
python3 tent_io/harness/odin_real_benchmark.py --out tent_io/harness/reports/odin_cli.ndjson
```

### TENT v4.1 (`tent_v41_external_benchmark/tent_benchmark_adapter.py`)

- Set **`TENT_INFERENCE_PATTERN=cli`** and any one of the bin env vars above.
- Same subprocess contract; `cwd` = the bundle directory.

```bash
export TENT_INFERENCE_PATTERN=cli
export HARNESS_CLI_BIN="/absolute/path/to/infer"
cd tent_io/harness/tent_v41_external_benchmark
python3 tent_benchmark_adapter.py --questions benchmark_questions_10_builtin.json
```

### Snapshot script

ODIN picks up CLI from the environment automatically.

```bash
export HARNESS_CLI_BIN="/absolute/path/to/infer"
python3 tent_io/harness/tools/run_intel_benchmark_snapshot.py --skip-tent-v41 --skip-gsm8k
```

TENT v4.1 defaults to **stub** in the snapshot; for CLI:

```bash
export TENT_INFERENCE_PATTERN=cli
export HARNESS_CLI_BIN="/absolute/path/to/infer"
python3 tent_io/harness/tools/run_intel_benchmark_snapshot.py --tent-v41-cli
```

## Scope (RC1)

- Accuracy claims are scoped to the **stated binary**, **question set**, and **environment** recorded in the artifact.
