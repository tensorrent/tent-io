# Full-spectrum testing and scoring

**Scope:** In-repo validation of **scoring math**, **CLI harness wiring**, **regression extract**, and a **fixture sweep** JSON. This is **not** a substitute for CI matrix testing or external benchmark campaigns; it guards **implementation drift** in the governance stack.

## What “full spectrum” covers here

| Layer | What is tested | Location |
|-------|----------------|----------|
| Intelligence scoring v1.1 | Golden vector, presets, replay consistency, external alignment, governance effect on AGI term | `tent_io/harness/tests/test_intelligence_scoring_core.py` |
| CLI inference | Env resolution order, `--prompt` / `--question-id` subprocess contract | `tent_io/harness/tests/test_cli_inference_harness.py` |
| Regression helper | `extract()` parity with scoring artifact shape | `tent_io/harness/tests/test_intelligence_regression_extract.py` |
| Fixture sweep | Sample `best_profile` JSON validates end-to-end score keys | `tent_io/harness/tests/fixtures/sweep_full_spectrum.json` |

**Core logic** used by both the CLI tool and tests: `tent_io/harness/intelligence_scoring_core.py` (`build_intelligence_scoring_output`).

## How to run (no extra packages)

```bash
cd tensorrent_tent_io_publish
python3 -m unittest discover -s tent_io/harness/tests -p "test_*.py" -v
```

## Aggregated runner + report

Runs the same unittest suite, then validates the fixture against `intelligence_scoring_core`, and writes:

- `tent_io/harness/reports/full_spectrum_harness.current.json`

```bash
python3 tent_io/harness/tools/run_full_spectrum_harness.py
```

Options:

- `--skip-tests` — only validate `--fixture` (default fixture path above).
- `--fixture PATH` — alternate sweep JSON.
- `--out-json PATH` — alternate report path.

## Scoring script (production path)

Unchanged CLI surface; implementation delegates to the core module:

```bash
python3 tent_io/harness/tools/compute_intelligence_scoring.py \
  --sweep-summary tent_io/harness/reports/expansion/llt_expansion_sweep.current.json \
  --out-json /tmp/score.json --out-md /tmp/score.md
```

## Optional: pytest

If you use a venv, `pip install pytest` and run `pytest tent_io/harness/tests` — tests are **unittest**-based, so pytest collects them as well.

## Related

- `INTELLIGENCE_TUNING.md` — operator weights and enforcement.
- `LLT_GOVERNANCE_AND_EVAL_STACK_WHITEPAPER.md` — artifact registry and workflow.
- `INTELLIGENCE_BENCHMARK_STATUS_AND_PLAN.md` — ODIN/TENT/GSM8K lanes vs blended scores.
