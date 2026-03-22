#!/usr/bin/env python3
"""
RC1 Harness: scan codebase for hallucination, problematic classifications, hyperbole, fluff.

Usage:
  ./harness/audit_claims_rc1.py                    # scan tent_io only (.md)
  ./harness/audit_claims_rc1.py --path .            # scan current dir
  ./harness/audit_claims_rc1.py --dev               # scan entire dev repo (from tent_io)
  ./harness/audit_claims_rc1.py --dev --seagate     # dev + Seagate (if mounted)
  ./harness/audit_claims_rc1.py --dev --all-text   # dev, all text-like extensions
  ./harness/audit_claims_rc1.py --json             # emit JSON
  ./harness/run_clean_sweep_rc1.sh                 # full clean sweep (dev + Seagate + all-text + report)

Output: file, line, pattern, suggested classification (H, PC, HB, FL, OC).
Case study: tent_io/docs/CASE_STUDY_HALLUCINATION_AND_PROBLEMATIC_CLAIMS.md
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Default root: tent_io when run from dev repo or tent_io
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
# Dev repo root (parent of tent_io when tent_io lives inside dev)
DEV_ROOT = ROOT.parent if (ROOT / "harness").exists() else ROOT
SEAGATE_DEFAULT = Path("/Volumes/Seagate 4tb")

# Patterns: (regex, classification, short label)
PATTERNS = [
    (r"\bworld[- ]?record\b", "OC", "world record claim"),
    (r"\bbreakthrough\b", "HB", "breakthrough"),
    (r"\brevolutionary\b", "HB", "revolutionary"),
    (r"\bparadigm\s*shift\b", "HB", "paradigm shift"),
    (r"\bunprecedented\b", "HB", "unprecedented"),
    (r"\bproof\s+that\b", "PC", "proof that"),
    (r"\bproves\s+that\b", "PC", "proves that"),
    (r"\bthis\s+document\s+proves\b", "PC", "document proves"),
    (r"\b100%\s*(accuracy|reliability|fidelity|pass|correct|success)\b", "OC", "100% claim"),
    (r"\b100%\s*(prime|prediction)\b", "OC", "100% prime/prediction"),
    (r"\bobsolete\b", "HB", "obsolete"),
    (r"\balways\s+wins\b", "HB", "always wins"),
    (r"\bgroundbreaking\b", "HB", "groundbreaking"),
    (r"\binfinite\b", "HB", "infinite (unqualified)"),
    (r"\babsolute\b", "HB", "absolute (unqualified)"),
    (r"\bnever\s+(fails?|wrong)\b", "OC", "never fails/wrong"),
    (r"\bzero\s+hallucination\b", "OC", "zero hallucination (scope)"),
    (r"\bvalidated\s+with\s+world", "H", "validated world-record"),
]

# Dirs to skip (anywhere in path)
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "gold_benchmarks", "archive", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", ".cache", "coverage", ".tox", ".mypy_cache",
    "site-packages", "vendor", "bower_components", ".idea", ".vscode",
}
# Don't flag audit docs that quote forbidden terms as examples
SKIP_FILES = {"CASE_STUDY_HALLUCINATION_AND_PROBLEMATIC_CLAIMS.md", "AUDIT_CRITERIA.md"}

# Extensions for --all-text
ALL_TEXT_EXTENSIONS = (".md", ".txt", ".tex", ".rst", ".py", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".sh", ".bash")


def scan_file(path: Path, patterns: list[tuple]) -> list[dict]:
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings
    for i, line in enumerate(text.splitlines(), 1):
        for regex, classification, label in patterns:
            if re.search(regex, line, re.IGNORECASE):
                findings.append({
                    "file": str(path),
                    "line": i,
                    "content": line.strip()[:200],
                    "classification": classification,
                    "pattern_label": label,
                })
    return findings


def collect_files(roots: list[Path], extensions: tuple[str, ...]) -> list[Path]:
    out = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(s in path.parts for s in SKIP_DIRS):
                continue
            if path.name in SKIP_FILES:
                continue
            if path.suffix.lower() not in extensions:
                continue
            # Skip very large files (e.g. > 2MB text)
            try:
                if path.stat().st_size > 2 * 1024 * 1024:
                    continue
            except OSError:
                continue
            out.append(path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="RC1 claim/hyperbole audit")
    ap.add_argument("--path", action="append", default=[], help="Path(s) to scan (can repeat)")
    ap.add_argument("--dev", action="store_true", help="Add entire dev repo root (parent of tent_io)")
    ap.add_argument("--seagate", action="store_true", help="Add Seagate volume (e.g. /Volumes/Seagate 4tb)")
    ap.add_argument("--extensions", type=str, default=".md", help="Comma-separated extensions e.g. .md,.txt (default: .md)")
    ap.add_argument("--all-text", action="store_true", help="Scan .md,.txt,.tex,.rst,.py,.json,.yml,.sh etc.")
    ap.add_argument("--json", action="store_true", help="Emit JSON only")
    ap.add_argument("--out", type=str, default=None, help="Write report to file (path)")
    args = ap.parse_args()

    roots = []
    for p in args.path:
        roots.append(Path(p).resolve())
    if args.dev:
        roots.append(DEV_ROOT)
    if args.seagate and SEAGATE_DEFAULT.exists():
        roots.append(SEAGATE_DEFAULT)
    if not roots:
        roots = [ROOT]

    if args.all_text:
        extensions = ALL_TEXT_EXTENSIONS
    else:
        extensions = tuple(e.strip() if e.startswith(".") else f".{e.strip()}" for e in args.extensions.split(","))

    all_findings = []
    seen_paths = set()
    for path in collect_files(roots, extensions):
        key = (path.resolve(),)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        all_findings.extend(scan_file(path, PATTERNS))

    # Dedupe by (file, line, pattern_label)
    seen = set()
    unique = []
    for f in all_findings:
        k = (f["file"], f["line"], f["pattern_label"])
        if k not in seen:
            seen.add(k)
            unique.append(f)
    all_findings = unique

    out_lines = []
    if args.json:
        payload = {"findings": all_findings, "count": len(all_findings), "roots": [str(r) for r in roots]}
        if args.out:
            Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        else:
            print(json.dumps(payload, indent=2))
        return 0

    if args.out:
        out_lines.append("# RC1 Clean sweep report\n")
        out_lines.append(f"Roots: {[str(r) for r in roots]}\n")
        out_lines.append(f"Extensions: {extensions}\n")
        out_lines.append(f"Total findings: {len(all_findings)}\n\n")
        out_lines.append("| File | Line | Class | Label | Excerpt |\n")
        out_lines.append("|------|------|-------|-------|--------|\n")
        for f in all_findings:
            excerpt = (f["content"][:80] + "…") if len(f["content"]) > 80 else f["content"]
            excerpt = excerpt.replace("|", "\\|").replace("\n", " ")
            rel = f["file"]
            for r in roots:
                try:
                    rel = str(Path(f["file"]).resolve().relative_to(r))
                except ValueError:
                    continue
                break
            out_lines.append(f"| {rel} | {f['line']} | {f['classification']} | {f['pattern_label']} | {excerpt} |\n")
        Path(args.out).write_text("".join(out_lines), encoding="utf-8")
        print(f"Wrote {len(all_findings)} findings to {args.out}", file=sys.stderr)
        return 0 if not all_findings else 1

    if not all_findings:
        print("RC1 audit: no pattern matches (OK).")
        return 0

    print("RC1 audit: possible hallucination / problematic classification / hyperbole / overclaim\n")
    print(f"Roots: {[str(r) for r in roots]}\n")
    print(f"{'File':<55} {'Ln':<5} {'Class':<4} {'Label':<25} Excerpt")
    print("-" * 125)
    for f in all_findings:
        excerpt = (f["content"][:55] + "…") if len(f["content"]) > 55 else f["content"]
        try:
            disp = str(Path(f["file"]).relative_to(roots[0])) if roots else Path(f["file"]).name
        except ValueError:
            disp = Path(f["file"]).name
        if len(disp) > 54:
            disp = "…" + disp[-51:]
        print(f"{disp:<55} {f['line']:<5} {f['classification']:<4} {f['pattern_label']:<25} {excerpt}")
    print("-" * 125)
    print(f"Total: {len(all_findings)}. See tent_io/docs/CASE_STUDY_HALLUCINATION_AND_PROBLEMATIC_CLAIMS.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())
