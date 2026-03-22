#!/usr/bin/env python3
import argparse
import json
import sys
import os

def extract_best_profile(data):
    """Extract best_profile from string or object."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        # Check for 'best_profile' key, then 'profile' or 'name' inside it
        bp = data.get('best_profile')
        if bp:
            if isinstance(bp, str):
                return bp
            if isinstance(bp, dict):
                return bp.get('profile') or bp.get('name')
    return None

def main():
    parser = argparse.ArgumentParser(description="Check for baseline profile drift.")
    parser.add_argument("--current", required=True, help="Path to current baseline JSON")
    parser.add_argument("--challenger", required=True, help="Path to challenger sweep summary JSON")
    parser.add_argument("--allow-change", action="store_true", help="Allow baseline change without alarm")
    args = parser.parse_args()

    try:
        with open(args.current, 'r') as f:
            current_data = json.load(f)
        with open(args.challenger, 'r') as f:
            challenger_data = json.load(f)
    except Exception as e:
        print(json.dumps({"status": "skipped", "reason": f"error_loading_files: {str(e)}"}))
        sys.exit(0)

    cur_bp = extract_best_profile(current_data)
    cha_bp = extract_best_profile(challenger_data)

    if not cur_bp or not cha_bp:
        print(json.dumps({
            "status": "skipped",
            "reason": "missing_best_profile",
            "current_best_profile": cur_bp,
            "challenger_best_profile": cha_bp,
            "allow_change": args.allow_change
        }))
        sys.exit(0)

    drifted = (cur_bp != cha_bp)
    
    output = {
        "status": "ok",
        "reason": None,
        "current_best_profile": cur_bp,
        "challenger_best_profile": cha_bp,
        "baseline_changed": drifted,
        "allow_change": args.allow_change
    }

    if drifted and not args.allow_change:
        output["status"] = "alarm"
        output["reason"] = "baseline_changed_without_approval"
        print(json.dumps(output))
        sys.exit(7)

    print(json.dumps(output))
    sys.exit(0)

if __name__ == "__main__":
    main()
