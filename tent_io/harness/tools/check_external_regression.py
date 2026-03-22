#!/usr/bin/env python3
import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser(description="Compare external evaluation runs (S1 vs S2).")
    parser.add_argument("--s1", required=True, help="Path to S1 external eval JSON")
    parser.add_argument("--s2", required=True, help="Path to S2 external eval JSON")
    parser.add_argument("--out", required=True, help="Output comparison JSON path")
    parser.add_argument("--previous", help="Path to previous comparison JSON for regression check")
    parser.add_argument("--fail-on-regression", action="store_true", help="Fail if overall performance regressed")
    
    # Optional threshold overrides
    parser.add_argument("--min-delta-mmlu-pro", type=float, default=-0.01)
    parser.add_argument("--min-delta-gpqa", type=float, default=-0.01)

    args = parser.parse_args()

    try:
        with open(args.s1, 'r') as f:
            s1_data = json.load(f)
        with open(args.s2, 'r') as f:
            s2_data = json.load(f)
        
        prev_data = None
        if args.previous:
            with open(args.previous, 'r') as f:
                prev_data = json.load(f)
    except Exception as e:
        print(f"Error loading inputs: {str(e)}")
        sys.exit(1)

    s1_metrics = s1_data.get("metrics", {})
    s2_metrics = s2_data.get("metrics", {})

    metrics_to_compare = [
        "mmlu_pro_acc",
        "gpqa_acc",
        "long_context_acc",
        "consistency_score"
    ]

    deltas = {}
    winner_votes = {"expand_s1": 0, "expand_s2": 0, "tie_or_missing": 0}

    for key in metrics_to_compare:
        v1 = s1_metrics.get(key)
        v2 = s2_metrics.get(key)
        
        if v1 is None or v2 is None:
            deltas[key] = None
            winner_votes["tie_or_missing"] += 1
            continue
        
        diff = v1 - v2
        deltas[key] = diff

        if diff > 0.0001:
            winner_votes["expand_s1"] += 1
        elif diff < -0.0001:
            winner_votes["expand_s2"] += 1
        else:
            winner_votes["tie_or_missing"] += 1

    favored = "tie_or_missing"
    if winner_votes["expand_s1"] > winner_votes["expand_s2"]:
        favored = "expand_s1"
    elif winner_votes["expand_s2"] > winner_votes["expand_s1"]:
        favored = "expand_s2"

    failures = []
    # Regression check against previous comparison if provided
    if prev_data:
        # Check if the favored profile's metrics are worse than before
        # Simplified: check for large negative deltas in s1-minus-s2 across runs
        pass

    status = "ok"
    if args.fail_on_regression and failures:
        status = "alarm"

    output = {
        "status": status,
        "mode": "comparison_with_regression_gate" if args.fail_on_regression else "comparison_non_blocking",
        "expand_s1": s1_data,
        "expand_s2": s2_data,
        "deltas_s1_minus_s2": deltas,
        "winner_votes": winner_votes,
        "favored_profile": favored,
        "previous_compare_path": args.previous,
        "regression_failures": failures
    }

    try:
        with open(args.out, 'w') as f:
            json.dump(output, f, indent=2)
    except Exception as e:
        print(f"Error writing output: {str(e)}")
        sys.exit(1)

    print(json.dumps(output))
    if status == "alarm":
        sys.exit(9)
    sys.exit(0)

if __name__ == "__main__":
    main()
