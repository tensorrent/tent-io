#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VOXEL_MIN_HYBRID_STEP_ACC="${VOXEL_MIN_HYBRID_STEP_ACC:-0.60}"
VOXEL_MIN_STACK_ACC="${VOXEL_MIN_STACK_ACC:-0.65}"
VOXEL_BEST_LINK="${VOXEL_BEST_LINK:-best_voxel_hybrid_step}"
VOXEL_SAMPLES_PER_STEP="${VOXEL_SAMPLES_PER_STEP:-40}"
VOXEL_SEED="${VOXEL_SEED:-19}"
LLT_EPOCHS="${LLT_EPOCHS:-1}"
LLT_HIDDEN_DIM="${LLT_HIDDEN_DIM:-48}"
LLT_MAX_TRAIN="${LLT_MAX_TRAIN:-512}"
LLT_MAX_TEST="${LLT_MAX_TEST:-256}"
LLT_MIN_TEST_ACC="${LLT_MIN_TEST_ACC:-0.20}"
LLT_MIN_MMLU_TEST_ACC="${LLT_MIN_MMLU_TEST_ACC:--1}"
LLT_MIN_CONVERSATIONAL_TEST_ACC="${LLT_MIN_CONVERSATIONAL_TEST_ACC:--1}"
LLT_MIN_EVAL_ACC="${LLT_MIN_EVAL_ACC:-0.20}"
LLT_MIN_EVAL_MMLU_ACC="${LLT_MIN_EVAL_MMLU_ACC:--1}"
LLT_MIN_EVAL_CONVERSATIONAL_ACC="${LLT_MIN_EVAL_CONVERSATIONAL_ACC:--1}"
LLT_MAX_REPLAY_DRIFT="${LLT_MAX_REPLAY_DRIFT:-1e-12}"
LLT_SPLIT_GATE_PROFILE="${LLT_SPLIT_GATE_PROFILE:-off}"
CONVERSATION_TRAIN_ROWS="${CONVERSATION_TRAIN_ROWS:-256}"
CONVERSATION_TEST_ROWS="${CONVERSATION_TEST_ROWS:-128}"
CONVERSATION_SEED="${CONVERSATION_SEED:-17}"
DISABLE_CONVERSATIONAL_LOGIC="${DISABLE_CONVERSATIONAL_LOGIC:-0}"
LLT_DRIFT_AUTO_LOG="${LLT_DRIFT_AUTO_LOG:-0}"
LLT_DRIFT_HISTORY_PATH="${LLT_DRIFT_HISTORY_PATH:-${REPO_ROOT}/tent_io/harness/reports/llt_drift_history.ndjson}"
LLT_DRIFT_KEEP_LAST="${LLT_DRIFT_KEEP_LAST:-0}"

EXTRA_ARGS=()
if [[ "${DISABLE_CONVERSATIONAL_LOGIC}" == "1" ]]; then
  EXTRA_ARGS+=(--disable-conversational-logic)
fi
case "${LLT_SPLIT_GATE_PROFILE}" in
  off)
    ;;
  strict_split_profile_v1)
    LLT_MIN_MMLU_TEST_ACC="0.215"
    LLT_MIN_CONVERSATIONAL_TEST_ACC="0.1384375"
    LLT_MIN_EVAL_MMLU_ACC="0.215"
    LLT_MIN_EVAL_CONVERSATIONAL_ACC="0.1384375"
    ;;
  strict_split_profile_v1_conservative)
    LLT_MIN_MMLU_TEST_ACC="0.205"
    LLT_MIN_CONVERSATIONAL_TEST_ACC="0.130"
    LLT_MIN_EVAL_MMLU_ACC="0.205"
    LLT_MIN_EVAL_CONVERSATIONAL_ACC="0.130"
    ;;
  *)
    echo "Unknown LLT_SPLIT_GATE_PROFILE: ${LLT_SPLIT_GATE_PROFILE}" >&2
    exit 2
    ;;
esac

CMD=(
  python3 "${REPO_ROOT}/tent_io/harness/run_full_stage_pipeline.py"
  --production
  --voxel-best-link "${VOXEL_BEST_LINK}"
  --voxel-samples-per-step "${VOXEL_SAMPLES_PER_STEP}"
  --voxel-seed "${VOXEL_SEED}"
  --voxel-min-hybrid-step-acc "${VOXEL_MIN_HYBRID_STEP_ACC}"
  --voxel-min-stack-acc "${VOXEL_MIN_STACK_ACC}"
  --llt-epochs "${LLT_EPOCHS}"
  --llt-hidden-dim "${LLT_HIDDEN_DIM}"
  --llt-max-train "${LLT_MAX_TRAIN}"
  --llt-max-test "${LLT_MAX_TEST}"
  --llt-min-test-acc "${LLT_MIN_TEST_ACC}"
  --llt-min-mmlu-test-acc "${LLT_MIN_MMLU_TEST_ACC}"
  --llt-min-conversational-test-acc "${LLT_MIN_CONVERSATIONAL_TEST_ACC}"
  --llt-min-eval-acc "${LLT_MIN_EVAL_ACC}"
  --llt-min-eval-mmlu-acc "${LLT_MIN_EVAL_MMLU_ACC}"
  --llt-min-eval-conversational-acc "${LLT_MIN_EVAL_CONVERSATIONAL_ACC}"
  --llt-max-replay-drift "${LLT_MAX_REPLAY_DRIFT}"
  --conversation-train-rows "${CONVERSATION_TRAIN_ROWS}"
  --conversation-test-rows "${CONVERSATION_TEST_ROWS}"
  --conversation-seed "${CONVERSATION_SEED}"
)
if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then
  CMD+=("${EXTRA_ARGS[@]}")
fi
if [[ "$#" -gt 0 ]]; then
  CMD+=("$@")
fi
"${CMD[@]}"

if [[ "${LLT_DRIFT_AUTO_LOG}" == "1" ]]; then
  python3 "${REPO_ROOT}/tent_io/harness/log_llt_drift_history.py" \
    --report "${REPO_ROOT}/tent_io/harness/reports/full_stage_pipeline.current.json" \
    --out "${LLT_DRIFT_HISTORY_PATH}" \
    --require-drift-pass
fi

if [[ "${LLT_DRIFT_KEEP_LAST}" =~ ^[0-9]+$ ]] && [[ "${LLT_DRIFT_KEEP_LAST}" -gt 0 ]]; then
  python3 "${REPO_ROOT}/tent_io/harness/trim_llt_drift_history.py" \
    --path "${LLT_DRIFT_HISTORY_PATH}" \
    --keep-last "${LLT_DRIFT_KEEP_LAST}"
fi
