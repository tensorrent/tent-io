#!/usr/bin/env python3
"""Generate prioritized merge plan from Antigravity V46 crosswalk report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def classify_action(layer: str, component: str, exists: bool) -> str:
    if exists:
        return "adopt"
    if layer == "L1":
        return "defer"
    if layer == "L2":
        if "SEGGCI" in component or "UPG" in component or "Executive" in component:
            return "stub"
        return "adopt"
    if layer == "L3":
        return "stub"
    return "defer"


def phase_of(layer: str, action: str) -> int:
    if action == "adopt" and layer == "L2":
        return 1
    if action == "stub" and layer == "L2":
        return 2
    if layer == "L3":
        return 3
    if layer == "L1":
        return 4
    return 5


def rationale(layer: str, component: str, action: str) -> str:
    if action == "adopt":
        return "Path exists in import; integrate directly with compatibility checks."
    if action == "stub":
        if layer == "L2":
            return "Kernel dependency expected by V46 but absent; add deterministic placeholder interface."
        return "External interface expected by V46 but absent; scaffold API contract before wiring runtime."
    if action == "defer":
        if layer == "L1":
            return "Foundational physics artifact; preserve as reference until implementation source is available."
        return "Not required for immediate kernel path; schedule after core integration."
    return "Manual review required."


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate auto-priority merge plan for Antigravity V46")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/antigravity_v46_blueprint_check.current.json"),
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/antigravity_v46_merge_plan.current.json"),
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/antigravity_v46_merge_plan.current.md"),
    )
    args = parser.parse_args()

    if not args.report.exists():
        print(json.dumps({"status": "error", "error": "report_missing", "report": str(args.report)}, indent=2))
        return 2

    report = json.loads(args.report.read_text(encoding="utf-8"))
    rows = report.get("rows", [])
    if not isinstance(rows, list):
        rows = []

    plan_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        layer = str(row.get("layer", ""))
        component = str(row.get("component", ""))
        exists = bool(row.get("exists", False))
        action = classify_action(layer, component, exists)
        phase = phase_of(layer, action)
        plan_rows.append(
            {
                "phase": phase,
                "layer": layer,
                "component": component,
                "declared_path": row.get("declared_path", ""),
                "resolved_path": row.get("resolved_path", ""),
                "exists": exists,
                "action": action,
                "rationale": rationale(layer, component, action),
            }
        )

    plan_rows.sort(key=lambda r: (int(r["phase"]), str(r["layer"]), str(r["component"])))
    counts = {"adopt": 0, "stub": 0, "defer": 0}
    for r in plan_rows:
        counts[str(r["action"])] += 1

    out = {
        "schema": "tent_io/antigravity_v46_merge_plan/v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_report": str(args.report),
        "summary": {
            "total": len(plan_rows),
            "adopt": counts["adopt"],
            "stub": counts["stub"],
            "defer": counts["defer"],
        },
        "plan_rows": plan_rows,
        "status": "ok",
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, ensure_ascii=True), encoding="utf-8")

    md_lines = [
        "# Antigravity V46 Merge Plan",
        "",
        f"- Generated: `{out['generated_at_utc']}`",
        f"- Source report: `{args.report}`",
        f"- Total items: `{out['summary']['total']}`",
        f"- Adopt: `{out['summary']['adopt']}` | Stub: `{out['summary']['stub']}` | Defer: `{out['summary']['defer']}`",
        "",
        "## Priority Order",
        "",
    ]
    for phase in sorted(set(int(r["phase"]) for r in plan_rows)):
        md_lines.append(f"### Phase {phase}")
        for r in [x for x in plan_rows if int(x["phase"]) == phase]:
            md_lines.append(
                f"- `{r['action']}` `{r['layer']}` `{r['component']}` -> `{r['declared_path']}` ({r['rationale']})"
            )
        md_lines.append("")

    args.out_md.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "out_json": str(args.out_json),
                "out_md": str(args.out_md),
                "summary": out["summary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
