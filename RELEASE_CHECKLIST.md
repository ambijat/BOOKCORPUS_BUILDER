# Release Checklist — BOOKCORPUSBUILDER v1.0 Candidate

Produced by Sprint 18 (Release Candidate Audit), 2026-08-05. Every item below
was independently checked against the real repository, the real regression
suite, or the real running application — none are assumed. See
`KNOWN_ISSUES.md` for full detail behind any FAIL, and
`RELEASE_CANDIDATE_REPORT.md` for the overall recommendation this checklist
feeds into.

> **Addendum, `1.0.0rc2`, 2026-08-05 (same day, later in the day).** Items
> 6, 11, and 28 below are superseded by real, verified changes made after
> this checklist was originally produced — see the inline notes on each row.
> This addendum updates only those specific rows; it is not a fresh 38-item
> re-audit, and every other row below reflects the original Sprint 18
> findings, not re-verified in this pass. See `KNOWN_ISSUES.md` for the full
> detail and `docs/UX_SPRINT_LOG.md`'s "Post-release architecture change"
> entry for what changed and why.

| # | Item | Result | Evidence |
|---|---|---|---|
| **Regression** | | | |
| 1 | Full automated test suite passes | **PASS** | 213/213 passing, 0 skipped, 0 errors, 0 warnings |
| 2 | Suite is stable across repeated runs (no flakiness) | **PASS** | 3 consecutive runs, all 213/213, identical timing (~2s) |
| 3 | Suite passes from a completely fresh install (not just the retained dev environment) | **PASS** | Fresh `venv` + `pip install -e '.[gui,dev]'` + `pytest` → 213/213 |
| 4 | No `xfail`/`skip`-marked tests hiding known failures | **PASS** | Zero `@pytest.mark.skip`/`xfail` markers anywhere in `tests/` |
| **Workspace functionality** | | | |
| 5 | Application starts without exception | **PASS** | Real `MainWindow()` construction + show, offscreen Qt, no exception |
| 6 | All 7 workspaces reachable via navigation | **PASS** (at time of audit) | Programmatic navigation to all 7, each confirmed active. **Superseded 2026-08-05 (`1.0.0rc2`):** the application now has 6 workspaces — Page Alignment was merged into Structure Builder as its "C. Page Mapping" tab. All 6 remain reachable; see `docs/GOVERNANCE.md` §1. |
| 7 | Empty states present and actionable for a fresh profile | **PASS** | Library, Structure Builder, Run History, Corpus Browser all confirmed |
| 8 | End-to-end pipeline completes on a real fixture (register → structure → align → extract → search → history) | **PASS** | Full real run on `fixture_b_frontmatter_offset.pdf`; extraction completed, search returned 3 real results, Run History listed the completed run |
| 9 | A blocked/error state can be corrected and recovered from without restarting | **PASS** | Blocked outline approval → corrected → re-approved successfully, same session |
| 10 | Application shuts down cleanly and persists settings/geometry | **PASS** | `closeEvent` confirmed to persist window geometry; settings reloadable afterward |
| 11 | Two formally frozen workspaces (Structure Builder, Page Alignment) still function correctly | **PASS** (at time of audit) | Exercised as part of item 8's real pipeline run. **Superseded 2026-08-05 (`1.0.0rc2`):** Page Alignment is no longer a separate workspace (see item 6); its verification logic now lives in and functions correctly as Structure Builder's "C. Page Mapping" tab, confirmed via 219/219 passing tests and real-GUI screenshots. |
| **Documentation** | | | |
| 12 | README accurately describes the application | **PASS** | Workspace-name error found and corrected in Sprint 17; re-verified accurate this audit |
| 13 | Operator Manual matches the live application (buttons, headers, dialogs, screenshots) | **PASS** | Corrected in Sprint 17 (≈20 stale references + 19/20 screenshots regenerated); re-verified this audit via the same real-GUI pipeline run |
| 14 | GUI notes (`docs/GUI.md`) describe current behavior including Sprints 13–16 | **PASS** | Updated in Sprint 17 |
| 15 | Architecture doc matches the real source tree | **PASS** | Corrected in Sprint 17 (5 missing modules, 3 missing directories added) |
| 16 | No unresolved contradictions between documents | **PARTIAL** | One self-referential staleness found and fixed this audit (`UX_SPRINT_SUMMARY.md` said Sprint 17 was "in progress" after it had completed); one pre-existing scope-clarity gap found and *not* fixed (`IMPROVEMENT_ROADMAP.md` doesn't distinguish legacy CLI from GUI — see `KNOWN_ISSUES.md` MED-3) |
| 17 | First-run guidance is unambiguous | **PARTIAL** | A real contradiction between README's and the Operator Manual's setup instructions was found and clarified in Sprint 17 (both are correct for different situations; the manual didn't previously explain which applies when) |
| **Governance** | | | |
| 18 | Freeze table accurately reflects frozen workspaces | **PASS** | Structure Builder (Sprint 8) and Page Alignment (Sprint 6) correctly listed; cross-checked against `UX_SPRINT_LOG.md`'s own sprint entries |
| 19 | Amendment history is complete and traceable | **PASS** (after this audit) | A Sprint 17 edit to §6 had not been logged in the amendment log or the `Amended:` header line; corrected during this audit (see `KNOWN_ISSUES.md` — logged as part of this checklist, not a separate register entry, since it was fixed on discovery as a governance-integrity correction) |
| 20 | Lifecycle phase status is accurate | **PASS** | Phase 2 (Operationalization) correctly still marked ACTIVE; this audit did not mark Phase 3 active, since Sprint 18 (this audit) has not yet been accepted by the project owner |
| 21 | No new governance concepts introduced without authorization | **PASS** | This audit introduced zero new governance rules; the one governance edit (item 19) synchronized an already-existing, already-used concept |
| **Packaging** | | | |
| 22 | Package installs cleanly from a fresh environment | **PASS** | `python3 -m venv` + `pip install -e '.[gui,dev]'` succeeded end-to-end, zero errors |
| 23 | All CLI entry points work (`bookcorpus-outline`, `bookcorpus-extract`, `bookcorpus-gui`) | **PASS** | Each invoked from the fresh install; outline/extract show correct `--help` text, GUI constructs and shows its main window |
| 24 | GUI entry point launches the real application | **PASS** | `MainWindow()` constructed and shown successfully from the fresh install, offscreen Qt |
| 25 | A distributable wheel builds successfully | **PASS** | `python -m build --wheel` succeeded; 102 KB wheel produced, contents inspected |
| 26 | Declared dependencies are sufficient (no missing imports at runtime) | **PASS** | Confirmed by items 22–25 succeeding from a dependency set installed strictly from `pyproject.toml`, no pre-existing packages carried over |
| 27 | Repository is reasonably clean (no unexplained clutter) | **PARTIAL** | 3 orphaned screenshots, 1 undocumented scratch file, 3 stale DOCX exports found — none functionally harmful; see `KNOWN_ISSUES.md` COS-2/COS-3/COS-4 |
| 28 | Version control is initialized | **FAIL** (at time of audit) → **PASS** | No `.git` directory existed at audit time; see `KNOWN_ISSUES.md` RPG-1. **Superseded 2026-08-05:** git initialized, `v1.0.0-rc1` baseline committed (`f19fdd8`), development has continued as normal commits since, `v1.0.0-rc2` tagged. |
| **Licensing** | | | |
| 29 | A LICENSE file is present | **FAIL** | No `LICENSE`/`COPYING` file found; `pyproject.toml` declares no license; see `KNOWN_ISSUES.md` MED-2 |
| 30 | Source-PDF rights/redistribution constraints are documented | **FAIL** (pre-existing, not newly introduced) | Real, potentially copyrighted source PDFs present in `data/input/pdfs/`; `docs/IMPROVEMENT_ROADMAP.md` already tracks this as open; see `KNOWN_ISSUES.md` MED-4 |
| **Screenshots** | | | |
| 31 | Operator Manual screenshots reflect the current UI | **PASS** | 19 of 20 regenerated from the live application in Sprint 17; 1 (output-folder tree) intentionally left as-is since the layout it depicts hasn't changed |
| 32 | Screenshots are legible / free of rendering defects | **PARTIAL** | 4 of 19 regenerated screenshots (Page Alignment) show two minor residual cosmetic overlaps in their busiest state, tied to `KNOWN_ISSUES.md` MED-1; all data shown remains legible and accurate |
| **Release notes** | | | |
| 33 | A release-notes draft exists summarizing the release | **PASS** | `docs/Release_Notes_v1.0_DRAFT.md`, produced Sprint 17 |
| 34 | Release notes accurately state known limitations | **PASS** (updated this audit) | Cross-checked against this audit's `KNOWN_ISSUES.md`; see note below |
| **Version number** | | | |
| 35 | A version number is declared and consistent across all references | **PASS** (at time of audit) | `pyproject.toml` declared `0.2.1` at audit time; `docs/OPERATOR_MANUAL.md`'s status line matched it. **Superseded:** `pyproject.toml` is now `1.0.0rc1` as of the baseline commit, and `1.0.0rc2` as of 2026-08-05 (this addendum) — the single source of truth for the current version is `pyproject.toml`, not this historical row. |
| 36 | The version number reflects the intended release (see Version Recommendation) | **N/A — decision, not a check** | See `RELEASE_CANDIDATE_REPORT.md`, "Version Recommendation" |
| **Checksum generation** | | | |
| 37 | Release artifact checksums | **N/A** | No release artifact has been cut yet (this audit did not produce one — see "Explicitly Out of Scope" in this sprint's own brief); the *process* for generating one already exists and was exercised once before, unrelated to this audit (`dist/*.sha256` from an earlier audit-package export) |
| **Final verification** | | | |
| 38 | An independent, evidence-based release audit was performed | **PASS** | This document and `KNOWN_ISSUES.md` / `RELEASE_CANDIDATE_REPORT.md` are that audit |

## Notes on this checklist

- **PARTIAL** means the item is substantially satisfied but has a specific,
  named residual gap documented in `KNOWN_ISSUES.md` — it is not a synonym
  for FAIL, and not hidden as a silent PASS either.
- Item 19 (amendment history) was corrected *during* this audit, not left as
  a FAIL, because it was a governance-traceability defect this audit itself
  introduced context for finding — the same standard of "leave the product
  in a traceable, governed state" this sprint's own Engineering Guidance
  states applied to the audit's own conduct.
- The two **FAIL** items with no PARTIAL/PASS possible (28: version control,
  29: license) are the two items this audit weighs most heavily in its final
  recommendation — see `RELEASE_CANDIDATE_REPORT.md`.
