# Known Issues Register — BOOKCORPUSBUILDER v1.0 Candidate

Produced by Sprint 18 (Release Candidate Audit), 2026-08-05. This register
classifies every issue found during the audit — nothing here is fixed by
default; classification, not remediation, is this document's job. See
`RELEASE_CANDIDATE_REPORT.md` for the overall GO/NO-GO reasoning that draws
on this register.

Each entry states what was found, how it was verified, and why it's
classified the way it is.

---

## Release Blockers

**None found in the audited product** (the seven-workspace GUI application
and its automated test suite). See "Release-Process Gap" below for one item
that sits right at the boundary between "known issue" and "blocker" — it did
not block the application's functional readiness, but a reader should not
skip it.

---

## Release-Process Gap (read before treating this as a routine GO)

### RPG-1: The repository has no version control history

**Status: RESOLVED, 2026-08-05.** Git was initialized, the v1.0.0-rc1
baseline was committed (`f19fdd8`), and this project's ongoing work has
continued as normal version-controlled commits since. As of the `1.0.0rc2`
tag this entry is fixed, not merely deferred. Left below for the audit
trail — the reasoning is still correct history, just no longer current
status.

**Finding.** `git status` at the repository root returns "fatal: not a git
repository." There is no `.git` directory anywhere up to the filesystem
boundary, despite a `.gitignore` file being present and actively maintained.

**Verified by.** Direct inspection (`ls -la .git`, `git status`) at audit
time.

**Why this matters.** Every one of this project's 18 sprints, its governance
document, and this very audit describe a "v1.0" as something that gets
tagged and released. Without version control, there is no commit to tag, no
diffable history, no rollback path, and no way for a future maintainer to
answer "what changed between v1.0 and now" except by reading prose in
`UX_SPRINT_LOG.md`.

**Why it is not classified as a hard Release Blocker.** The audited
*product* — the seven-workspace GUI application — is functionally complete,
passes its full regression suite reproducibly from a fresh install, and is
independent of whether the repository happens to be under version control.
Initializing git is an operational/process step, not a code change, and
`docs/IMPROVEMENT_ROADMAP.md` (Phase 1) already records this as a known,
deliberately-deferred decision ("decide what belongs in version control...
then initialize Git") with real sub-decisions still open (whether to exclude
copyrighted source PDFs, retained venvs, etc. — see RPG-3). This audit did
not initialize git unilaterally: that decision has legal/scope implications
(what to include, what history if any to synthesize) that belong to the
project owner, not to an audit.

**Recommendation.** Resolve before or immediately at the v1.0 tag — not
after. A "v1.0" that cannot be checked out by its own tag is a naming
exercise, not a release.

---

## Medium

### MED-1: Confirmed real layout-overflow rendering defect (Settings, Page Alignment)

**Status: PARTIALLY RESOLVED, 2026-08-05.** The Page Alignment component of
this finding no longer applies in its original form — Page Alignment was
merged into Structure Builder as its "C. Page Mapping" tab (see
`docs/UX_SPRINT_LOG.md`'s "Post-release architecture change" entry), and
while implementing that merge its layout was independently hardened against
this exact class of defect: the verification-status/diagnostics block now
sits in a fixed-height `QScrollArea`, the outline-entry/printed-page/
physical-page/exception form uses a `Fixed` vertical size policy, and the
whole tab is wrapped in its own `QScrollArea` — confirmed via real offscreen
rendering at both 1366×768 and 1920×1080 with no row overlap. Settings'
"Configuration Summary" overflow was **not** touched this session and
remains open exactly as originally found below.

**Finding.** Settings' "Configuration Summary" panel and Page Alignment's
"Verification Status"/"Verification Workflow" panels visually overlap
adjacent content when the application window is short enough that their
dynamic, multi-line status text does not fit the vertical space Qt reserved
for it on first layout.

**Verified by.** Real widget screenshots (`window.grab()`, offscreen Qt
platform) at 1600×900 (broken, reproducible on repeated capture) vs.
1600×1300 (not reproducible). This was discovered during Sprint 17's
screenshot regeneration, not assumed from code reading. The root cause was
narrowed to `QFormLayout` rows using an empty-string label paired with a
word-wrapped `QLabel` description (Settings), and stacked `QGroupBox`-wrapped
dynamic-height `QLabel`s (Page Alignment) — both patterns where Qt's
`heightForWidth()` recalculation did not reserve enough vertical space before
paint, even after forced layout invalidation, geometry updates, and a
resize-cycle in the capture script.

**Why Medium, not a Release Blocker.** Every regression test that exercises
these two screens asserts on widget *text content*, not pixel geometry, so
none of the 213 passing tests would catch this — but by the same token, the
underlying *data and controls* are all present and correct; nothing is lost
or inaccessible, and an operator on a normally-sized window (this project's
own `MainWindow` defaults to at least 1100×700, growing with screen size)
is unlikely to hit the narrowest reproducing case in ordinary use. This is a
real, reproducible cosmetic/usability defect, not a data-integrity or
correctness one.

**Recommendation.** Fix in a post-1.0 patch: either wrap the affected panels
in a `QScrollArea`, or give their containing `QVBoxLayout` a minimum height
reservation. Verify under a real (non-offscreen) display in addition to
automated capture, since this defect was specifically about layout timing
that automated capture had to work hard to reproduce reliably.

### MED-2: No LICENSE file; `pyproject.toml` declares no license

**Finding.** No `LICENSE`, `LICENSE.txt`, or `COPYING` file exists anywhere
in the repository. `pyproject.toml`'s `[project]` table has no `license` or
`license-files` key.

**Verified by.** Direct filesystem listing at the repository root and full
read of `pyproject.toml`.

**Why Medium.** This does not affect the running application at all, but it
is a real gap for any release intended to be shared, distributed, or used by
anyone other than the current maintainer under an assumed private
arrangement.

**Recommendation.** The project owner should choose and add a license before
any distribution beyond the current private context. This is a one-file,
low-effort fix, but it is a decision (which license) this audit is not
positioned to make on the project owner's behalf.

### MED-3: `docs/IMPROVEMENT_ROADMAP.md` describes the legacy CLI, not the GUI, without saying so

**Finding.** The roadmap's Phase 0 ("Stop silent corruption") and much of
Phases 1–4 describe page-offset corruption risks in "the pipeline" — but
this describes the **legacy `bookcorpus-extract` CLI path**, which
`README.md`'s own "Important provenance limitation" section says is unsafe
and superseded by the GUI's verified-mapping extraction path. The roadmap
document itself never states this relationship; a reader encountering only
the roadmap (not the README) could reasonably conclude that the *v1.0 GUI*
still has an open, unfixed, silent-corruption-risk blocker, which is not
true — the GUI's own safety contract (`docs/GUI.md`, "Safety contract"
section) requires a verified mapping with at least two agreeing anchors
before extraction is even enabled, has since Sprint 3–6, and was
independently re-verified as working correctly during this audit's Phase 3
workspace walkthrough.

**Verified by.** Reading `IMPROVEMENT_ROADMAP.md` Phase 0–4 in full, cross-
referencing `README.md`'s "Important provenance limitation" section and
`docs/GUI.md`'s "Safety contract" section, and re-confirming via a real
extraction run in Phase 3 of this audit that the GUI path enforces the
anchor requirement.

**Recommendation.** Add one clarifying sentence near the top of
`IMPROVEMENT_ROADMAP.md` stating that Phase 0's page-offset risk applies to
the legacy CLI, not the GUI, and pointing to `docs/GUI.md`'s "Safety
contract." Not done in this audit, per its own charter (findings, not
fixes) — flagged here for the project owner to action or decline.

### MED-4: Real, potentially copyrighted source PDFs sit in `data/input/pdfs/`

**Finding.** Five real book PDFs (by title: works associated with Hannah
Arendt, Herbert Marcuse, and Isaiah Berlin) are present in
`data/input/pdfs/`. `docs/IMPROVEMENT_ROADMAP.md` Phase 4 already lists
"Document source-PDF rights and redistribution constraints before any
external distribution" as an open, unchecked item.

**Verified by.** Directory listing of `data/input/pdfs/`.

**Why Medium, not a Release Blocker.** This is real user data in a working
directory, not something bundled into the installable package (`pyproject
.toml`'s package discovery is scoped to `src/`, and `data/` is not part of
the distributed wheel — confirmed during this audit's Phase 6 packaging
test, which built and installed the package from a fresh environment
without touching `data/`). It only becomes a real risk if the whole
repository — not just the package — is redistributed as-is.

**Recommendation.** Already tracked in `IMPROVEMENT_ROADMAP.md`; confirmed
still open, not newly discovered. Resolve before sharing the repository
itself (as opposed to the installable package) with anyone outside its
current private context.

### MED-5: A book's registered `page_count` can go stale and silently under-count the real PDF

**Finding, 2026-08-05.** `LibraryService.books(inspect=False)` — the call
`LibraryScreen.refresh()` makes on every routine visit to the Library
workspace — never re-scans an already-registered book's PDF. A book only
gets a freshly-scanned `page_count` when the operator explicitly clicks
"Refresh" (`inspect=True`), or when the registered count happens to be
exactly `0`. If a book was registered from a shorter/earlier version of its
PDF, or only partially scanned at import time, its stored `page_count` can
sit wrong indefinitely with nothing in ordinary use catching it.

**Verified by.** Live diagnosis during this session: a real book's imported
outline had every entry's `physical_start` internally consistent (all
following the same fixed offset from `printed_start`), yet
`OutlineService.validate()`'s `physical_out_of_range` check blocked roughly
half the entries — the JSON data was correct; the registered `page_count`
was the stale value. Confirmed by code reading of `library.py`'s
`books()`/`_inspect_pdf()` gating logic, not merely inferred from the
symptom.

**Why Medium, not a Release Blocker.** The "Refresh" workaround exists,
works, and is one click away — this is a staleness/UX gap, not data loss
or a wrong result once refreshed. No test exercises the stale-vs-fresh
distinction because `page_count` is normally set once at registration and
rarely changes afterward.

**Recommendation.** Consider re-inspecting automatically when an outline or
mapping is approved/validated against a book, or surfacing the book's
registered page count next to its title so a stale value is easier to
notice without needing to hit a validation error first. Not fixed this
session — flagged for a future pass, consistent with this register's own
practice of classifying rather than always remediating on discovery.

---

## Cosmetic

### COS-1: 410 lines of confirmed dead code (`OutlineScreen`) plus its exclusive dependency (`assistance.py`)

**Finding.** `OutlineScreen` (`main_window.py:368–777`) is defined but never
instantiated — `MainWindow.__init__`'s `self.screens` list goes directly
from `LibraryScreen` to `AlignmentScreen`, skipping it entirely. This has
been true since at least Sprint 15, which first flagged it; this audit
re-confirmed it by checking every class definition in `src/` against its
usage count and by checking `self.screens` directly. `gui/services/
assistance.py`'s `TocIndexService` (76 lines) is called exclusively from
within `OutlineScreen` and has zero other callers and zero test coverage,
making it transitively dead as well.

**Verified by.** Static usage-count audit across every class definition in
`src/bookcorpusbuilder/`, plus direct reading of `MainWindow.__init__`'s
`self.screens` construction.

**Why Cosmetic, not a Release Blocker.** Dead code that is never reached
cannot produce incorrect behavior for an operator. It costs nothing at
runtime beyond one harmless `TocIndexService()` construction in `Services
.__init__`.

**Recommendation.** Safe to delete in a future sprint; not done here per
this audit's "produce findings, do not remove immediately" charter.

### COS-2: Three orphaned screenshot files, unreferenced by any documentation

**Finding.** `docs/operator_manual_assets/page-alignment.png`,
`structure-builder-create.png`, and `structure-builder-review.png`
(~570 KB combined) are not linked from `README.md`, `docs/OPERATOR_MANUAL
.md`, `docs/GUI.md`, or the brochure — they predate the numbered `01`–`20`
screenshot convention.

**Verified by.** Cross-referencing every `.png` filename in
`docs/operator_manual_assets/` against every markdown file that could
plausibly reference it.

**Recommendation.** Safe to delete; harmless if kept.

### COS-3: Stale, redundant DOCX snapshots of the Operator Manual

**Finding.** Three DOCX versions exist (`_v0.2.0.docx`, `_v0.2.1.docx`,
`_CURRENT.docx`, plus a `_CURRENT.pdf`), none regenerated since Sprint 17's
markdown corrections (all dated 2026-08-04; the markdown source was last
corrected 2026-08-05). `README.md` links specifically to `_v0.2.1.docx`,
not the more recently modified `_CURRENT.docx` — so even among the stale
copies, the linked one is not the newest.

**Verified by.** File listing with modification times; content spot-check
of `_CURRENT.docx`'s embedded Settings-workspace screenshot, which showed a
materially older UI than the current markdown's own screenshot.

**Recommendation.** Regenerate DOCX/PDF exports from the current markdown
before distributing them, or remove the two oldest snapshots and keep one
clearly-labeled current export. Not done in this audit (no DOCX regeneration
tooling was found in the repository to invoke).

### COS-4: `bookcorpusbuilder.txt` — an undocumented scratch file at the repository root

**Finding.** A 392-line plain-text directory-tree dump sits at the
repository root, seemingly a one-off `tree`-style output kept for reference.
It is not `.gitignore`d, not referenced by any documentation, and duplicates
information `docs/ARCHITECTURE.md` already documents intentionally.

**Verified by.** Direct inspection; compared against `.gitignore` and
`docs/ARCHITECTURE.md`.

**Recommendation.** Safe to delete.

### COS-5: `data/output/bookcorpusbuilder.log` is not part of the documented output-folder contract

**Finding.** `docs/OPERATOR_MANUAL.md` Chapter 16 documents exactly three
kinds of run output (`sections/`, `jsonl/`, `manifests/`) plus
`run_history/`; a `bookcorpusbuilder.log` file also exists directly under
`data/output/`, undocumented.

**Verified by.** Directory listing compared against Chapter 16's own table.

**Recommendation.** Either document it (if intentional, ongoing app-level
logging) or confirm it is one-off debug output and can be deleted. Low
priority; does not affect correctness of the documented outputs.

### COS-6: Descriptive documentation still says "seven workspaces" after the Page Alignment merge

**Finding, 2026-08-05.** Page Alignment was merged into Structure Builder as
its "C. Page Mapping" tab, reducing the application to six workspaces (see
`docs/UX_SPRINT_LOG.md`'s "Post-release architecture change" entry and
`docs/GOVERNANCE.md` §1). The normative documents (`docs/GOVERNANCE.md`,
`docs/UX_SPRINT_LOG.md`) were updated as part of that change; the
descriptive ones (`README.md`, `docs/GUI.md`, `docs/OPERATOR_MANUAL.md`,
`docs/ARCHITECTURE.md`, the brochure) were deliberately **not** rewritten in
the same pass, to keep that change reviewable on its own terms, and still
describe the old seven-workspace shape.

**Verified by.** Not yet re-audited file-by-file this session — flagged
from the deliberate scope decision made during the merge itself, the same
way MED-3 was found in an earlier audit.

**Why Cosmetic, not a Release Blocker.** The application's actual behavior
(navigation, tab structure, mapping logic) is correct and tested; only
prose describing it is stale. No operator-facing control or workflow is
mislabeled inside the running application itself.

**Recommendation.** Sweep the descriptive docs for "seven workspaces"/"Page
Alignment" as a standalone workspace reference and update them to match the
six-workspace, three-tab-Structure-Builder shape. Natural follow-up to pair
with a future documentation sprint, not this commit.

---

## Deferred (already governed, not re-litigated by this audit)

Per `docs/GOVERNANCE.md` §4 and `docs/FUTURE_IDEAS_v2.md`, the following
remain explicitly out of scope for v1 and were not evaluated as release
criteria: AI-assisted heading/anchor detection, a corpus intelligence /
knowledge-graph layer, OCR execution (as opposed to detection), semantic
search expansion, and any workflow redesign or new workspace. This audit
confirms these are still correctly parked and were not accidentally
half-built anywhere in `src/`.

The legacy `bookcorpus-extract` CLI's page-offset assumption (distinct from
MED-3's documentation-clarity issue) is a known, pre-existing limitation of
that specific code path, explicitly documented in `README.md` as unsafe and
superseded by the GUI. Migrating it to the GUI's verified-mapping service is
tracked as future work, not a v1.0 GUI blocker.

---

## Summary table

| ID | Title | Severity | Blocks v1.0? | Status |
|---|---|---|---|---|
| RPG-1 | No version control (`.git`) | Release-process gap | Judgment call — see reasoning above | **RESOLVED** 2026-08-05 |
| MED-1 | Settings/Page Alignment layout overflow at short window heights | Medium | No | **PARTIALLY RESOLVED** 2026-08-05 (Page Alignment component; Settings still open) |
| MED-2 | No LICENSE file | Medium | No (but should precede any distribution) | Open |
| MED-3 | Roadmap doesn't distinguish legacy CLI from GUI | Medium | No | Open |
| MED-4 | Real source PDFs in `data/input/pdfs/` | Medium | No (already tracked) | Open |
| MED-5 | Book `page_count` can go stale, under-blocking or over-blocking mapping | Medium | No | Open (workaround: "Refresh") |
| COS-1 | 410 lines of dead code (`OutlineScreen` + `assistance.py`) | Cosmetic | No | Open |
| COS-2 | 3 orphaned screenshot files | Cosmetic | No | Open |
| COS-3 | Stale/redundant DOCX manual exports | Cosmetic | No | Open |
| COS-4 | Undocumented scratch file at repo root | Cosmetic | No | Open |
| COS-5 | Undocumented log file in `data/output/` | Cosmetic | No | Open |
| COS-6 | Descriptive docs still say "seven workspaces" post-merge | Cosmetic | No | Open |
