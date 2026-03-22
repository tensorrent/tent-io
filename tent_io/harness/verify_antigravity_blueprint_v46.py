#!/usr/bin/env python3
"""Crosswalk Antigravity V46 blueprint against a local build tree."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def exists(path: Path) -> bool:
    return path.exists()


def build_blueprint_entries() -> list[dict[str, str]]:
    # Paths are modeled from the user-provided V46 blueprint.
    return [
        # Layer 1
        {"layer": "L1", "component": "Quantum ΔI gap note", "path": "documentation/three_open_gaps_analysis.md"},
        {"layer": "L1", "component": "T4' converse gap note", "path": "documentation/three_open_gaps_analysis.md"},
        {"layer": "L1", "component": "su(3) attractor report", "path": "documentation/TR-2026-FF06_FINAL.tex"},
        {"layer": "L1", "component": "Selection flow verifier", "path": "selection_full.py"},
        {"layer": "L1", "component": "Chirality verifier", "path": "chirality_test.py"},
        # Layer 2
        {"layer": "L2", "component": "CDCL core", "path": "crates/cdcl/src/lib.rs"},
        {"layer": "L2", "component": "CDCL persistence", "path": "crates/cdcl/src/persist.rs"},
        {"layer": "L2", "component": "CDCL resonance", "path": "crates/cdcl/src/resonance.rs"},
        {"layer": "L2", "component": "Routing entry", "path": "crates/routing/src/lib.rs"},
        {"layer": "L2", "component": "SEGGCI static routing", "path": "crates/routing/src/seggci_static.rs"},
        {"layer": "L2", "component": "SEGGCI logic chain", "path": "crates/routing/src/seggci_logic.rs"},
        {"layer": "L2", "component": "SEGGCI council gate", "path": "crates/routing/src/seggci_council.rs"},
        {"layer": "L2", "component": "UPG constants", "path": "crates/routing/src/upg_constants.rs"},
        {"layer": "L2", "component": "Executive identity", "path": "crates/executive/src/lib.rs"},
        {"layer": "L2", "component": "Executive consensus", "path": "crates/executive/src/consensus.rs"},
        # Layer 3
        {"layer": "L3", "component": "API server", "path": "crates/api_server/src/main.rs"},
        {"layer": "L3", "component": "OmniForge web", "path": "omniforge_web.py"},
        {"layer": "L3", "component": "OmniForge orchestrator", "path": "omniforge_orchestrator.py"},
        # Layer 4 references
        {"layer": "L4", "component": "Master plan reference", "path": "task.md"},
        {"layer": "L4", "component": "Historical walkthrough", "path": "walkthrough.md"},
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Antigravity Sovereign Stack V46 blueprint paths")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/Users/coo-koba42/dev/archive/imports/omniforge-seggci-complete-3"),
        help="Root of Antigravity/sovereign build to verify.",
    )
    parser.add_argument(
        "--alt-root",
        type=Path,
        default=Path("/Users/coo-koba42/dev/archive/imports/omniforge-seggci-complete-3/omniforge-phase0"),
        help="Optional nested root to check when paths are rooted under a subfolder.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/Users/coo-koba42/dev/tent_io/harness/reports/antigravity_v46_blueprint_check.current.json"),
    )
    args = parser.parse_args()

    entries = build_blueprint_entries()
    rows: list[dict[str, Any]] = []
    found = 0
    for entry in entries:
        rel = Path(entry["path"])
        p1 = args.root / rel
        p2 = args.alt_root / rel
        p = p1 if exists(p1) else p2
        ok = exists(p)
        if ok:
            found += 1
        rows.append(
            {
                "layer": entry["layer"],
                "component": entry["component"],
                "declared_path": entry["path"],
                "resolved_path": str(p if ok else p1),
                "exists": ok,
            }
        )

    constants = {
        "wallace_exponent_phi": "1.61803398875",
        "severity_ratio_alpha": "79/21",
        "band_reject_threshold": "<2 top band and <0.55 density",
    }
    verification_commands = {
        "rust": "cargo check --all-targets",
        "physics": "python3 chirality_test.py",
        "mesh": "TcpStream echo STATS to port 4370",
    }

    out = {
        "schema": "tent_io/antigravity_blueprint_v46_check/v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "root": str(args.root),
        "alt_root": str(args.alt_root),
        "total_entries": len(rows),
        "found_entries": found,
        "missing_entries": len(rows) - found,
        "constants": constants,
        "verification_commands": verification_commands,
        "rows": rows,
        "status": "ok" if found == len(rows) else "partial",
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({"status": out["status"], "out": str(args.out), "found": found, "total": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
