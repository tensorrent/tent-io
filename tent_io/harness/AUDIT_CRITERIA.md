# Audit criteria (Phase 18 walkthrough + RC1 harness)

- **Avoid:** "groundbreaking," "revolutionary," "paradigm shift," "unprecedented," "proof that," "proves that," "absolute," "infinite" (unless defined), "world record" (unless cited), "breakthrough" (unqualified), "100% reliability/accuracy" (unless scoped), "obsolete," "always wins."
- **Use:** "reported," "in the model," "in the harness," "as implemented," "design," "metaphor," "as-reported," "sovereign framing."
- **Scope:** Claims limited to the stated test environment and codebase; no unqualified physical or universal claims.
- **Refs:** See `../papers_audited/AUDIT_CRITERIA.md` in dev repo when available.

## RC1 harness (Release Candidate 1)

The codebase is treated as a release candidate: claims and language are sifted and classified before lock.

- **Script:** `harness/audit_claims_rc1.py` — scans for hallucination, problematic classification, hyperbole, fluff, overclaim.
- **Case study:** `docs/CASE_STUDY_HALLUCINATION_AND_PROBLEMATIC_CLAIMS.md` — taxonomy (H, PC, HB, FL, OC, OK) and findings with corrected language.
- **Run:** `./harness/audit_claims_rc1.py` (from tent_io); optional `--path .` or `--json`.
- **Classifications:** H = Hallucination, PC = Problematic classification, HB = Hyperbole, FL = Fluff, OC = Overclaim, OK = Accepted after revision.
- **Standard env rule:** RC1 is set as the default workspace rule in `dev/.cursor/rules/rc1-standard.mdc` (always apply). New and edited prose in this repo should follow RC1; the agent uses it as the language standard.
