# Release Candidate Report — BOOKCORPUSBUILDER v1.0

**Prepared by:** Sprint 18 — Release Candidate Audit (independent release
auditor role, not development)
**Date:** 2026-08-05
**Scope:** The seven-workspace PySide6 desktop application and its
supporting service layer, as governed by `docs/GOVERNANCE.md` §1.

This report answers one question with evidence: **is BOOKCORPUSBUILDER
ready to be released as Version 1.0?** It draws on `KNOWN_ISSUES.md` (full
findings register) and `RELEASE_CHECKLIST.md` (item-by-item PASS/FAIL), both
produced alongside this report. Neither this report nor its companions
changed any application code; see "Behaviour intentionally unchanged" in the
accompanying chat report for the two governance-traceability edits that
*were* made, and why they were treated as in-scope for an audit.

---

## Executive Summary

BOOKCORPUSBUILDER's **application** — the seven-workspace GUI, its service
layer, and its documentation — is in excellent, release-ready condition.
Eighteen sprints of iterative UX work, cross-cutting product refinement, and
a documentation pass have produced a consistent, well-tested, accurately
documented product. This audit's independent verification (213/213 tests
passing reproducibly from a fresh install; a full real-GUI walkthrough of
every workspace including startup, shutdown, edge cases, and recovery; a
successful fresh install, wheel build, and entry-point smoke test) found
**zero functional defects** and **zero application-behavior release
blockers**.

However, the **release-engineering surroundings** of the application are not
ready: the repository has no version control history at all, and no license
is declared. Neither of these is a defect in the software itself, but both
are things a reasonable definition of "released, versioned software"
requires, and neither was something this audit was authorized to decide
unilaterally (see `KNOWN_ISSUES.md`, RPG-1 and MED-2).

**Verdict: GO WITH KNOWN ISSUES.** The product is ready. The release
process around it is not quite — specifically, initialize version control
and add a license before (or as part of) cutting the actual v1.0 tag.
Neither blocks continued use of the application in its current, private
context.

---

## Product Overview

BOOKCORPUSBUILDER turns book-length PDFs into a human-reviewed outline, a
verified printed-to-physical page mapping, and a section-level corpus (TXT,
JSONL, manifest), with full run history and provenance back to the exact
source PDF page. The desktop GUI (PySide6) provides seven workspaces —
Library, Structure Builder, Page Alignment, Extract, Corpus Browser, Run
History, Settings — each matured through its own UX sprint(s) and then
refined by four further cross-cutting sprints (shared task lifecycle,
keyboard/navigation, error recovery, and visual/linguistic consistency). Two
workspaces (Structure Builder, Page Alignment) are formally frozen per
`docs/GOVERNANCE.md` §7.

---

## Test Summary

| Metric | Result |
|---|---|
| Tests passing | 213 / 213 |
| Tests failing | 0 |
| Tests skipped | 0 |
| Tests unstable across repeated runs | 0 (3 consecutive runs, identical result) |
| Passes from a completely fresh install | Yes (independently re-verified this audit, not assumed from prior sprints) |
| Warnings emitted | 0 |
| Real-GUI workspace walkthrough | 26/26 checks passed — startup, navigation (all 7), empty states (4 workspaces), full real pipeline (register → structure → align → extract → search → history), blocked-state recovery, and clean shutdown with settings persistence |

Full methodology in `RELEASE_CHECKLIST.md`, items 1–11.

---

## Documentation Summary

Every core document (`README.md`, `docs/OPERATOR_MANUAL.md`, `docs/GUI.md`,
`docs/ARCHITECTURE.md`, `docs/GOVERNANCE.md`, `docs/UX_SPRINT_SUMMARY.md`,
`docs/Release_Notes_v1.0_DRAFT.md`, `docs/DEVELOPER_HANDOVER.md`) was
compared against the live application. Sprint 17 had already corrected the
large body of staleness accumulated over 16 prior sprints; this audit
re-verified those corrections against a fresh real-GUI walkthrough and found
them accurate, plus caught and fixed one new staleness this same audit's
work introduced (`UX_SPRINT_SUMMARY.md` describing Sprint 17 as "in
progress" after it had completed).

Two residual documentation issues were found and are recorded, not fixed,
in `KNOWN_ISSUES.md`: `docs/IMPROVEMENT_ROADMAP.md` doesn't clarify that its
Phase 0 corruption-risk findings describe the legacy CLI, not the GUI (MED-3
— a real scope-clarity gap, not a factual error); and three DOCX exports of
the Operator Manual are stale relative to Sprint 17's markdown corrections
(COS-3).

Full methodology in `RELEASE_CHECKLIST.md`, items 12–17.

---

## Governance Summary

`docs/GOVERNANCE.md`'s freeze table, lifecycle phase, and feature-acceptance
rule are internally consistent with `docs/UX_SPRINT_LOG.md`'s actual sprint
history (17 completed sprint entries, cross-checked one-by-one against the
freeze table's two frozen-workspace claims). One traceability gap was found
and corrected during this audit: a Sprint 17 edit to §6 (Lifecycle) had not
been logged in the amendment log or the header's `Amended:` line, as the
document's own §8 self-amendment protocol requires. This was fixed on
discovery — not deferred — because it is a governance-integrity correction
(making an already-authorized change traceable), not a product or scope
change requiring new authorization.

No new governance concepts were introduced by this audit, and none of the
five workspaces outside the frozen two were found to have drifted from their
accepted sprint outcomes.

Full methodology in `RELEASE_CHECKLIST.md`, items 18–21.

---

## Known Issues

Full register: `KNOWN_ISSUES.md`. Summary:

- **Release Blockers (application-level): none found.**
- **Release-Process Gap:** no version control history (RPG-1) — the single
  finding this report weighs most heavily; see "Risks" below.
- **Medium (4):** the layout-overflow rendering defect in Settings/Page
  Alignment (MED-1, real and reproducible, cosmetic in impact); no LICENSE
  file (MED-2); a documentation scope-clarity gap in the improvement roadmap
  (MED-3); real source PDFs present in the working tree with rights not yet
  documented, already tracked pre-existing (MED-4).
- **Cosmetic (5):** confirmed dead code (410 lines: `OutlineScreen` +
  `assistance.py`), orphaned screenshots, stale DOCX exports, an
  undocumented scratch file, and an undocumented log file.

None of the Medium or Cosmetic items were fixed in this audit, per its own
charter — findings were classified, not remediated.

---

## Deferred Work

Confirmed still correctly out of scope and not accidentally half-built
anywhere in `src/`: AI-assisted heading/anchor detection, a corpus
intelligence/knowledge-graph layer, OCR execution, semantic search
expansion, and any workflow redesign or new workspace (`docs/GOVERNANCE.md`
§4, `docs/FUTURE_IDEAS_v2.md`). The legacy `bookcorpus-extract` CLI's
page-offset limitation is a known, pre-existing, explicitly-documented gap
in that specific code path, distinct from and not blocking the GUI.

---

## Risks

1. **No version control (RPG-1).** The most significant finding of this
   audit. A "v1.0" that cannot be checked out by a tag, diffed against a
   prior state, or attributed to a commit is not a normal software release
   in the conventional sense — it is a labeled snapshot of a working
   directory. This does not risk the application's *correctness*, but it
   risks the project's ability to *prove* what shipped, roll back a bad
   change, or onboard a future contributor with standard tooling. This
   audit did not initialize git itself: doing so involves real decisions
   (what history, if any, to synthesize; what to exclude — copyrighted
   PDFs, retained venvs) that belong to the project owner, and
   `docs/IMPROVEMENT_ROADMAP.md` already records this as a deliberately
   open decision, not an oversight this audit is positioned to close
   unilaterally.
2. **No license (MED-2).** Low risk to the application's operation, real
   risk to anyone outside the current private context trying to use,
   modify, or redistribute it.
3. **The layout-overflow defect (MED-1)** is real and reproducible but
   cosmetic — no data is lost or hidden, and it was not caught by 213
   passing tests because none of them assert on pixel geometry. This is
   itself worth noting as a category of risk: the test suite is strong for
   *behavior* and *state*, weaker for *visual layout*. Recommend a real
   (non-offscreen) display verification pass before the next UI-affecting
   change to either affected screen.
4. **Everything else in `KNOWN_ISSUES.md`** is low-risk, well-understood,
   and either already tracked pre-existing or newly classified as Cosmetic.

---

## Version Recommendation

```text
Recommended Version

v1.0.0-rc1
```

**Justification.** The application itself has earned "v1.0" — feature-complete
per `docs/GOVERNANCE.md` §1, thoroughly tested, thoroughly documented, and
independently re-verified by this audit with zero functional defects found.
It has not yet earned the unqualified "v1.0.0" tag, because two release-
process prerequisites (version control, license) remain open, and "rc1"
honestly signals "this is the candidate; two known, named, non-functional
gaps stand between here and the final tag" rather than either overclaiming
readiness or discarding eighteen sprints of real, verified work by calling
it something less than a release candidate. Once RPG-1 and MED-2 are
resolved and this report is not contradicted by that work, `v1.0.0` itself
is justified without needing another full audit — a confirmation pass
against just those two items should suffice.

---

## Final Verdict

```text
GO WITH KNOWN ISSUES
```

**Reasoning.** Every check this audit could perform against the running
application, its test suite, its documentation, and its governance came back
positive — not "acceptable with caveats," but genuinely clean: 213/213
tests, 26/26 real-GUI checks, zero application-level release blockers, and a
documentation/governance set that is now internally consistent. That is a
GO on the product.

It is not an unqualified GO because two release-process items (no version
control, no license) are real, unresolved, and — in the case of version
control — unusual enough for a "v1.0" that a reader of this report should
not be able to miss them by skimming to a single word. "GO WITH KNOWN
ISSUES" is the verdict that keeps both truths visible: the software is
ready; two things around the software are not yet. Resolving RPG-1 and
MED-2 is a small amount of work relative to the eighteen sprints already
invested, and neither requires reopening any frozen workspace or any
already-accepted product decision.
