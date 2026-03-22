#!/usr/bin/env python3
import argparse
import json
import sys

def get_metrics(data):
    """Extract metrics from best_profile entry in summary."""
    # The whitepaper implies reading metrics from sweep summary
    bp = data.get('best_profile', {})
    if not isinstance(bp, dict):
        return {}
    
    metrics = {
        "final_test_acc": bp.get("final_test_acc"),
        "mmlu_test_acc": bp.get("mmlu_test_acc"),
        "conversational_logic_test_acc": bp.get("conversational_logic_test_acc"),
        "drift": bp.get("drift")
    }
    return metrics

def main():
    parser = argparse.ArgumentParser(description="Check for performance regression.")
    parser.add_argument("--current", required=True, help="Current sweep summary JSON")
    parser.add_argument("--previous", required=True, help="Previous sweep summary JSON")
    parser.add_argument("--min-delta-final-test-acc", type=float, default=0.0)
    parser.add_argument("--min-delta-mmlu-test-acc", type=float, default=0.0)
    parser.add_argument("--min-delta-conversational-test-acc", type=float, default=0.0)
    parser.add_argument("--max-delta-drift", type=float, default=0.1)
    args = parser.parse_args()

    try:
        with open(args.current, 'r') as f:
            current_data = json.load(f)
        with open(args.previous, 'r') as f:
            previous_data = json.load(f)
    except Exception as e:
        print(json.dumps({"status": "skipped", "reason": f"error_loading_files: {str(e)}"}))
        sys.exit(0)

    cur_metrics = get_metrics(current_data)
    pre_metrics = get_metrics(previous_data)

    if not any(pre_metrics.values()):
        print(json.dumps({
            "status": "skipped",
            "reason": "missing_previous_metrics",
            "current": args.current,
            "previous": args.previous
        }))
        sys.exit(0)

    failures = []
    deltas = {}

    # Define checks
    checks = [
        ("final_test_acc", args.min_delta_final_test_acc, "min"),
        ("mmlu_test_acc", args.min_delta_mmlu_test_acc, "min"),
        ("conversational_logic_test_acc", args.min_delta_conversational_test_acc, "min"),
        ("drift", args.max_delta_drift, "abs_max")
    ]

    for key, threshold, mode in checks:
        cur_val = cur_metrics.get(key)
        pre_val = pre_metrics.get(key)
        
        if cur_val is None or pre_val is None:
            deltas[f"delta_{key}"] = None
            continue

        delta = cur_val - pre_val
        deltas[f"delta_{key}"] = delta

        if mode == "min" and delta < threshold:
            failures.append(f"{key}: delta {delta:.4f} < threshold {threshold:.4f}")
        elif mode == "abs_max" and abs(delta) > threshold:
            failures.append(f"{key}: abs_delta {abs(delta):.4f} > threshold {threshold:.4f}")

    status = "alarm" if failures else "ok"
    
    output = {
        "status": status,
        "reason": "regression_detected" if failures else None,
        "current": args.current,
        "previous": args.previous,
        "current_metrics": cur_metrics,
        "previous_metrics": pre_metrics,
        "deltas": deltas,
        "thresholds": {
            "min_delta_final_test_acc": args.min_delta_final_test_acc,
            "min_delta_mmlu_test_acc": args.min_delta_mmlu_test_acc,
            "min_delta_conversational_test_acc": args.min_delta_conversational_test_acc,
            "max_delta_drift": args.max_delta_drift
        },
        "failures": failures
    }

    print(json.dumps(output))
    if status == "alarm":
        sys.exit(8)
    sys.exit(0)

if __name__ == "__main__":
    main()
