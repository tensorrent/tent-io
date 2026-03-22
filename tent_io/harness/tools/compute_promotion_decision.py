#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="Compute promotion decision state.")
    parser.add_argument("--internal-summary", required=True, help="Path to internal sweep summary JSON")
    parser.add_argument("--external-compare", required=True, help="Path to external comparison JSON")
    parser.add_argument("--out", required=True, help="Output decision JSON path")
    parser.add_argument("--history-out", required=True, help="Path to append NDJSON history")
    parser.add_argument("--alignment-required-runs", type=int, default=1)
    parser.add_argument("--min-internal-margin", type=float, default=0.005)
    parser.add_argument("--min-external-vote-margin", type=int, default=1)

    args = parser.parse_args()

    try:
        with open(args.internal_summary, 'r') as f:
            int_data = json.load(f)
        with open(args.external_compare, 'r') as f:
            ext_data = json.load(f)
    except Exception as e:
        print(f"Error loading inputs: {str(e)}")
        sys.exit(1)

    # 1. Resolve internal winner
    # Internal summary best_profile is usually an object with 'profile' key
    int_bp = int_data.get("best_profile", {})
    int_winner = int_bp.get("profile") if isinstance(int_bp, dict) else None
    int_margin = int_bp.get("margin") or 0.0 # hypothetical margin from sweep

    # 2. Resolve external winner
    ext_winner_profile = ext_data.get("favored_profile") # expand_s1 | expand_s2 | tie_or_missing
    # Map 'expand_sX' to the actual profile name if possible
    # In check_external_regression, expand_s1 is s1_data
    s1_name = ext_data.get("expand_s1", {}).get("profile")
    s2_name = ext_data.get("expand_s2", {}).get("profile")

    ext_winner_name = None
    if ext_winner_profile == "expand_s1":
        ext_winner_name = s1_name
    elif ext_winner_profile == "expand_s2":
        ext_winner_name = s2_name

    ext_vote_margin = ext_data.get("winner_votes", {}).get(ext_winner_profile, 0) - \
                     ext_data.get("winner_votes", {}).get("tie_or_missing", 0)

    # 3. Compute Alignment
    aligned = False
    contested = False
    
    if int_winner and ext_winner_name:
        if int_winner == ext_winner_name:
            aligned = True
        else:
            contested = True
    
    # 4. Load/Track Streak
    streak = 0
    if os.path.exists(args.history_out):
        try:
            with open(args.history_out, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_row = json.loads(lines[-1])
                    if last_row.get("aligned") and aligned:
                        streak = last_row.get("aligned_streak", 0) + 1
                    elif aligned:
                        streak = 1
        except:
            streak = 1 if aligned else 0
    else:
        streak = 1 if aligned else 0

    # 5. Determine State
    if not int_winner or not ext_winner_name:
        state = "insufficient_signal"
    elif contested:
        state = "contested"
    elif not aligned:
        state = "insufficient_signal" # redundant but safe
    else:
        # Aligned
        meets_int = int_margin >= args.min_internal_margin
        meets_ext = ext_vote_margin >= args.min_external_vote_margin
        
        if streak < args.alignment_required_runs:
            state = "aligned_pending_confirmation"
        elif not (meets_int and meets_ext):
            state = "aligned_but_margin_insufficient"
        else:
            state = "aligned_ready_for_promotion"

    allowed = (state == "aligned_ready_for_promotion")

    output = {
        "status": "ok",
        "decision_state": state,
        "promotion_allowed": allowed,
        "internal_winner": int_winner,
        "external_winner": ext_winner_name,
        "aligned": aligned,
        "contested": contested,
        "alignment_required_runs": args.alignment_required_runs,
        "aligned_streak": streak,
        "internal_margin": int_margin,
        "min_internal_margin": args.min_internal_margin,
        "external_vote_margin": ext_vote_margin,
        "min_external_vote_margin": args.min_external_vote_margin,
        "meets_internal_margin": (int_margin >= args.min_internal_margin),
        "meets_external_margin": (ext_vote_margin >= args.min_external_vote_margin),
        "internal_summary": args.internal_summary,
        "external_compare": args.external_compare,
        "history_path": args.history_out
    }

    # Write decision
    try:
        with open(args.out, 'w') as f:
            json.dump(output, f, indent=2)
    except Exception as e:
        print(f"Error writing decision: {str(e)}")
        sys.exit(1)

    # Write history
    history_row = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "decision_state": state,
        "promotion_allowed": allowed,
        "internal_winner": int_winner,
        "external_winner": ext_winner_name,
        "aligned": aligned,
        "contested": contested,
        "aligned_streak": streak,
        "alignment_required_runs": args.alignment_required_runs,
        "internal_margin": int_margin,
        "external_vote_margin": ext_vote_margin,
        "meets_internal_margin": (int_margin >= args.min_internal_margin),
        "meets_external_margin": (ext_vote_margin >= args.min_external_vote_margin)
    }
    
    try:
        with open(args.history_out, 'a') as f:
            f.write(json.dumps(history_row) + "\n")
    except Exception as e:
        print(f"Error writing history: {str(e)}")
        # Don't fail the whole script just because history write failed

    print(json.dumps(output))
    sys.exit(0)

if __name__ == "__main__":
    main()
