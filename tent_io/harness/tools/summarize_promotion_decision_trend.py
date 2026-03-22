#!/usr/bin/env python3
import argparse
import json
import os
import sys

def main():
    parser = argparse.ArgumentParser(description="Summarize promotion decision trend.")
    parser.add_argument("--history", required=True, help="Path to promotion_decision.history.ndjson")
    parser.add_argument("--out-json", required=True, help="Output trend JSON path")
    parser.add_argument("--out-md", required=True, help="Output trend Markdown report path")
    parser.add_argument("--window", type=int, default=10, help="Window for recent trend analysis")

    args = parser.parse_args()

    if not os.path.exists(args.history):
        print(f"History file not found: {args.history}")
        sys.exit(0)

    rows = []
    try:
        with open(args.history, 'r') as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    except Exception as e:
        print(f"Error reading history: {str(e)}")
        sys.exit(1)

    if not rows:
        print("No history rows found.")
        sys.exit(0)

    total_points = len(rows)
    recent_rows = rows[-args.window:]
    window_points = len(recent_rows)

    def count_states(data):
        counts = {}
        for row in data:
            s = row.get("decision_state", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    counts_all = count_states(rows)
    counts_recent = count_states(recent_rows)

    contested_recent = counts_recent.get("contested", 0)
    contested_ratio = contested_recent / window_points if window_points > 0 else 0
    
    aligned_ready_recent = counts_recent.get("aligned_ready_for_promotion", 0)
    ready_ratio = aligned_ready_recent / window_points if window_points > 0 else 0

    regime = "balanced"
    if contested_ratio > 0.5:
        regime = "contested_dominant"
    elif ready_ratio > 0.6:
        regime = "aligned_dominant"

    output_json = {
        "status": "ok",
        "history_path": args.history,
        "total_points": total_points,
        "window": args.window,
        "window_points": window_points,
        "latest_state": rows[-1].get("decision_state"),
        "counts_all": counts_all,
        "counts_recent": counts_recent,
        "contested_ratio_recent": contested_ratio,
        "regime_label": regime
    }

    try:
        with open(args.out_json, 'w') as f:
            json.dump(output_json, f, indent=2)
    except Exception as e:
        print(f"Error writing JSON: {str(e)}")

    # Write Markdown
    md = f"# Promotion Decision Trend Report\n\n"
    md += f"**Latest State:** `{output_json['latest_state']}`\n"
    md += f"**Regime:** `{regime}`\n\n"
    md += f"## Recent Window (last {window_points} points)\n"
    for state, count in counts_recent.items():
        pct = (count / window_points) * 100
        md += f"- {state}: {count} ({pct:.1f}%)\n"
    
    md += f"\n## All-Time Statistics ({total_points} total points)\n"
    for state, count in counts_all.items():
        md += f"- {state}: {count}\n"

    try:
        with open(args.out_md, 'w') as f:
            f.write(md)
    except Exception as e:
        print(f"Error writing Markdown: {str(e)}")

    print(json.dumps(output_json))
    sys.exit(0)

if __name__ == "__main__":
    main()
