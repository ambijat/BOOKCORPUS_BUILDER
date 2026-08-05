# BOOKCORPUSBUILDER v1.0 — Release Notes (DRAFT)

> **This is a draft, originally prepared during Sprint 17 (Documentation &
> Knowledge Transfer) and updated during Sprint 18 (Release Candidate
> Audit). It is not an announcement.** No release has been cut, tagged, or
> published. Do not distribute this as though v1.0 has shipped. Sprint 18's
> full findings live in `../KNOWN_ISSUES.md`, `../RELEASE_CHECKLIST.md`, and
> `../RELEASE_CANDIDATE_REPORT.md` (repository root) — this document's
> "Known limitations" section below is a summary of those, not a
> replacement for them.

## What BOOKCORPUSBUILDER v1.0 is

A seven-workspace PySide6 desktop application that turns book-length PDFs
into a human-reviewed outline, a verified printed-to-physical page mapping,
and a section-level corpus (TXT, JSONL, and manifest), with full run history
and provenance back to the exact source PDF page.

## Major UX improvements (Sprints 1–16)

**Per-workspace maturation (Sprints 1–12):** every one of the seven
workspaces — Library, Structure Builder, Page Alignment, Extract, Corpus
Browser, Run History, Settings — received a dedicated UX programme: status
cockpits, semantic classification, conflict resolution and diagnostics,
research-grade search and filtering, and live configuration validation. See
[`UX_SPRINT_SUMMARY.md`](UX_SPRINT_SUMMARY.md) for the one-line outcome of
each sprint, or [`UX_SPRINT_LOG.md`](UX_SPRINT_LOG.md) for full detail.

**Cross-cutting product refinement (Sprints 13–16):**
- A shared background-task lifecycle: every long-running operation shows a
  consistent running/succeeded/failed state, and a failed task always resets
  the workspace that started it rather than leaving it visually stuck.
- Consistent, safe keyboard and confirmation behavior: destructive actions
  default their confirmation to "No," keyboard focus returns to the right
  place after Add/Delete/Move actions, and Enter submits where an operator
  would expect it to.
- A single error-reporting structure everywhere: every error dialog states a
  plain-language Reason and a concrete next step, with the full technical
  exception always available (never discarded) behind an expandable "Show
  Details" section.
- One consistent visual and linguistic style across all seven workspaces:
  Title Case controls and headers, one icon per concept, and one wording per
  action (e.g., "Open Source PDF" reads identically everywhere it appears).

## Governance milestones

- `docs/GOVERNANCE.md` formally adopted 2026-08-04, establishing the v1
  feature-acceptance rule (5-point test), the priority order for v1 work, and
  what is explicitly out of scope for v1 (AI assistants, knowledge graphs,
  topic modeling, new workspaces — all parked in `FUTURE_IDEAS_v2.md`).
- **Two workspaces are formally frozen**, each after its own planned UX
  programme was accepted:
  - Page Alignment (Workspace 3) — frozen as of Sprint 6.
  - Structure Builder (Workspace 2) — frozen as of Sprint 8.
  Every subsequent touch to either workspace (Sprints 13–16) was explicitly
  flagged as interaction/wording-only, never business logic, and is
  documented at the point it happened.
- The other five workspaces are mature and stable but not formally frozen —
  they may still receive workspace-specific enhancement, subject to the same
  5-point acceptance rule.

## Known limitations

- **The source PDF preview is native extracted text, not a rendered PDF
  canvas.** Opening the exact page in a real PDF viewer is delegated to the
  operating system's default PDF viewer.
- **OCR is detected, not performed.** Settings reports whether a `tesseract`
  binary is present on `PATH`; nothing in the application invokes OCR at any
  stage. A scanned (image-only) PDF must be OCR'd externally, producing a
  real text layer, before this application can process it meaningfully.
- **The legacy `bookcorpus-extract` CLI has not been migrated to the GUI's
  verified page-mapping service** and still assumes printed page numbers are
  physical page numbers. Treat its output as unverified; the GUI's own
  extraction path is the safe one.
- **A layout-overflow issue was discovered during this sprint's screenshot
  verification pass**: Settings' Configuration Summary panel and Page
  Alignment's Verification Status/Workflow panels can visually overlap
  adjacent content when the application window is short enough that their
  dynamic, multi-line status text does not fit in the space initially
  reserved for it (confirmed reproducible at a 1600×900 window size; not
  reproducible at 1600×1300). This is a **documentation-discovered,
  code-unchanged finding** — per this sprint's own charter, it was not fixed
  here. Recommended for Sprint 18's regression/hardening pass.
- **Focused/offscreen GUI tests do not fully substitute for a display-capable
  environment.** The regression suite runs headless (`QT_QPA_PLATFORM=
  offscreen`); the layout-overflow issue above was only found by rendering
  real widget screenshots through that same offscreen path, not by the
  existing test suite, which asserts on widget *state* and *text* rather than
  pixel layout.
- **The repository has no version control history** (`git status` reports
  "not a git repository") and **no LICENSE file is present.** Both are
  release-process gaps, not application defects, discovered during Sprint
  18's audit. See `../KNOWN_ISSUES.md` (RPG-1, MED-2) for full detail — these
  two items carry the most weight in that sprint's final recommendation.
- 410 lines of confirmed dead code (`OutlineScreen` and its exclusive
  dependency `gui/services/assistance.py`), three orphaned screenshot files,
  stale DOCX exports of the Operator Manual, and a documentation-scope gap in
  `IMPROVEMENT_ROADMAP.md` were also found during Sprint 18's audit — all
  classified Cosmetic or Medium, none blocking. Full detail:
  `../KNOWN_ISSUES.md`.

## Deferred to v2 (not in scope for v1)

Per `docs/GOVERNANCE.md` §4 and `docs/FUTURE_IDEAS_v2.md`: automatic
heading/anchor detection assistants, a corpus intelligence/knowledge-graph
layer, OCR execution (as opposed to detection), semantic search expansion,
and any workflow redesign or new workspace. None of these were implemented,
prototyped, or scoped during v1 development — they remain parked exactly
where `FUTURE_IDEAS_v2.md` records them.

## Test status

213 automated tests passing (`pytest`, offscreen Qt platform), spanning
service-layer unit tests and real-widget GUI tests across all seven
workspaces. Reconfirmed stable across 3 consecutive runs and from a
completely fresh install (not just the retained development environment)
during Sprint 18's audit.

## Sprint 18 audit outcome

Sprint 18 (Release Candidate Audit) is complete. It made no product changes
— per its own charter, it audited the existing product rather than improving
it, correcting only documentation/governance-traceability issues discovered
along the way (not application behavior). Its full findings, checklist, and
final GO/NO-GO recommendation are in `../KNOWN_ISSUES.md`,
`../RELEASE_CHECKLIST.md`, and `../RELEASE_CANDIDATE_REPORT.md`
respectively — this draft does not restate them. Two items from that audit
(no version control, no license) are load-bearing enough that they should be
resolved before this draft is finalized into an actual release announcement,
regardless of the audit's overall recommendation.
  version is `0.2.1`; whether this becomes the literal `v1.0` tag, or v1.0 is
  a milestone name distinct from the package version, is a decision for
  Sprint 18, not assumed here).
- A release checklist and the actual v1.0 release candidate.
