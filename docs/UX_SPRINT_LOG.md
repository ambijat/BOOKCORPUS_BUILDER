# UX Sprint Log — BOOKCORPUSBUILDER

Running record of the UX-hardening sprints against the seven-workspace GUI
(`docs/GOVERNANCE.md` Phase 2, Priority A). Each entry is written after the
sprint is verified against the real PySide6 application, not just unit
tests. See `docs/GOVERNANCE.md` for the acceptance rule every sprint below
was checked against.

---

## Sprint 1 — Workspace 5 (Corpus Browser) initialization

Date: 2026-08-04

### Completed

- Auto-select the newest completed run on entry.
- Auto-refresh results on entry — no manual "Search" press required.
- Run dropdown refreshes results immediately on change (was previously
  wired to nothing — a real bug, not just a wording gap).
- Last selected run is remembered across restarts (`browser.last_run` in
  settings) and takes priority over "auto-pick newest".
- Three distinct empty-state messages: no extractions exist anywhere yet,
  this run has no sections, or the current filters matched nothing.

### Already existed (verified, left unchanged)

- Splitter position persistence (`configure_splitter`, `browser.results`).

### Deferred (not in scope for this sprint)

- Per-result metadata wording (dense but functional).
- Human-readable run labels — moved to Sprint 2 (Run History).

### Verified

- Real GUI, offscreen Qt platform, actual widget clicks (book selection,
  workspace navigation, run-dropdown switch), across 5 scenarios including
  a book with zero extractions and a simulated app restart.
- Full test suite: 100/100 passing.

---

## Sprint 2 — Workspace 6 (Run History) UX

Date: 2026-08-04

### Completed

- Book column shows the PDF filename instead of the internal book-id hash.
- Double-clicking a completed run opens it directly in Corpus Browser
  (book + run pre-selected), reusing `BrowserScreen`'s existing loading
  path rather than adding a parallel one.
- Status column color-coded (completed / running / failed / cancelled),
  reusing the exact palette already established for Page Alignment's
  resolution states (`RESOLUTION_COLORS`) rather than inventing a new one.
- Started timestamp rendered as `YYYY-MM-DD HH:MM:SS` instead of raw ISO
  8601; underlying `RunRecord.started_at` is untouched.
- Output column shows `runs/<run_id>` instead of the full absolute path,
  with the full path available as a tooltip.
- Column widths rebalanced for the new content (Book wider for filenames,
  Output narrower since it no longer holds a full path).

### Already existed (verified, left unchanged)

- Run ordering: `HistoryService.records()` already returns newest-first;
  preserved and reverified after the presentation changes.

### Discovered, not fixed here

- No table in the application (Run History included) has clickable
  column-header sorting — `setSortingEnabled` is not used anywhere in
  `main_window.py`. This is a cross-cutting, app-wide gap, not a
  Run-History-specific regression, so it was left alone rather than
  added to one table inconsistently with the other six.

### Deferred (not in scope for this sprint)

- Extraction engine, corpus model, page mapping, schemas — untouched, as
  required by the sprint brief.

### Verified

- Real GUI, offscreen Qt platform: book filename resolution, status
  colors, timestamp formatting, output-column tooltip, and the
  double-click → Corpus Browser handoff (including the "only completed
  runs" guard for a non-completed row).
- Full test suite: 100/100 passing.

---

## Sprint 3 — Workspace 4 (Extract) UX polish

Date: 2026-08-04

### Completed

- Extraction Readiness panel: replaces the bare "PASSED / All extraction
  checks passed." message with a structured summary (Book, Outline,
  Page Mapping, Validation, Output Folder, Status), plus grouped
  Warnings/Blocking-issues lists when dry run doesn't pass cleanly.
- Progress checklist: replaces the developer-oriented `1/8`, `2/8` log
  lines with a per-section `✓ Title` list; skipped sections are marked
  `⊘ Title` instead of looking identical to written ones.
- Progress completion state: a dedicated status label now reads
  "✓ Extraction Complete" once the run finishes, instead of leaving the
  progress bar looking merely paused at 100%.
- Completion Summary: Book, sections expected/written/skipped/failed,
  elapsed time (computed from the existing `RunRecord.started_at` /
  `completed_at`), and a colored status line.
- Next-step actions: "Open Corpus Browser" (navigates to Workspace 5 and
  pre-selects the run just extracted, reusing the same
  navigate-and-preselect pattern Sprint 2 added to Run History's
  double-click handler), "Open Output Folder", and "Open Run Folder"
  (both reuse the existing `open_path` helper). All three are disabled
  until a run completes successfully.
- Output folder readability: both the readiness panel and the completion
  summary show `<parent>/<name>` instead of the full path, with the full
  path preserved as a tooltip — same convention Sprint 2 established for
  Run History's Output column (`short_output_path`, a new module-level
  helper reusing that exact logic; Run History's own inline version was
  left untouched, since it's outside Workspace 4).
- Detailed log retained underneath, unchanged in content, so operators
  who want the raw per-issue/per-page trace still have it.

### Already existed (verified, left unchanged)

- `preflight()` / `ExtractionService` / extraction engine, page mapping,
  outline approval, manifest/JSONL writing — untouched. The new panels
  only read fields already present on `RunRecord`, `ValidationIssue`, and
  the dry-run issue list; nothing was recomputed.
- `MainWindow.run_task`'s threading/progress-signal wiring — reused
  as-is via the existing `with_progress` / `progress_slot` parameters.

### Discovered, not fixed here

- If `ExtractionService.run()` raises mid-run (the `status == "failed"`
  path), the exception surfaces through `run_task`'s generic
  `worker.failed` → error-dialog path and `ExtractScreen.completed()` is
  never called — so the progress panel is left in its "in progress"
  state rather than showing a failure state. This is existing, shared
  behavior in `MainWindow.run_task` (used by every workspace, not just
  Extract), so fixing it was out of scope for a single-workspace UX
  sprint; flagging it for a future sprint that's allowed to touch shared
  GUI infrastructure.

### Verified

- Full test suite: 106/106 passing (100 pre-existing + 6 new in
  `tests/test_extract_screen.py`, covering the ready/blocked readiness
  states, the progress checklist including the skipped-section marker,
  the completion summary, and both next-step navigation actions).
- Real GUI, offscreen Qt platform, against the actual `MainWindow` (not
  a fake): registered a real PDF fixture
  (`docs/operator_manual_assets/fixtures/fixture_a_normal.pdf`) through
  the real `LibraryService`, approved a real outline and page mapping
  through the real `OutlineService`/`MappingService`, then drove the
  real `ExtractScreen` with `QTest.mouseClick` — including a genuine
  `QThread`-backed extraction run pumped through the Qt event loop (no
  faked services). Confirmed: blocked dry run shows NOT READY/BLOCKED
  when mapping isn't approved; ready dry run shows READY FOR
  EXTRACTION/SAFE TO EXTRACT; the extraction actually ran and wrote 3
  real `.txt` files whose contents matched the source PDF; the
  checklist, completion summary, and next-step buttons updated
  correctly; "Open Corpus Browser" pre-selected the correct run;
  "Open Output Folder"/"Open Run Folder" (with `QDesktopServices.openUrl`
  mocked) targeted the correct paths. Verification run against an
  isolated scratch project directory — the real `data/` corpus was never
  touched.

---

## Sprint 4 — Workspace 3 (Page Alignment: Anchor Workflow) UX polish

Date: 2026-08-04

### Completed

- Empty-state guidance: a new book with an approved outline but zero
  anchors now opens to "Begin by selecting the first chapter and adding
  your first verification anchor." (or, if the outline itself doesn't
  exist yet, "No outline entries yet — build and approve the outline in
  Structure Builder…") instead of a bare, technical BLOCKING diagnostic
  dump.
- New **segment guidance panel**: a dedicated label below the Segments
  table that turns "needs a second anchor" into an actionable
  instruction — e.g. "Add one more anchor anywhere between printed pages
  11 and 49 to confirm this offset," using the real segments already on
  either side (or "anywhere after printed page X" when there's no later
  segment to bound the range). Clicking a row in the Segments table
  updates this panel to describe that specific segment, without a full
  re-render.
- **Post-anchor acceptance feedback**: after `add_anchor()`, a new panel
  immediately shows "✓ Anchor accepted", whether the affected segment is
  now confirmed or still needs one more anchor, and the next recommended
  anchor — reusing the existing `suggest_next_anchor()` call already
  used elsewhere on the screen.
- **Changed-row highlighting**: the Segments-table row and Mapping
  Preview row(s) affected by the anchor just added are bolded for that
  one render cycle (presentation only — a `QFont` change, no new
  colors, no data changes) so the operator doesn't have to hunt through
  the tables to see what changed.
- **Richer "Suggested Next"**: expanded from a one-line "Suggested next:
  Title" into a structured panel (Section / Printed page / Reason / Next
  action). "Reason" is derived honestly from real, currently-known state
  (no anchors yet vs. no confirmed segment yet vs. outside every
  confirmed segment) — it does not claim to know an unverified physical
  page in advance.
- **Completion guidance**: once every segment is confirmed and every
  outline entry resolves, but the mapping isn't approved yet, the status
  panel now shows "✓ All segments confirmed / ✓ All outline entries
  resolved / Next Step: Verify and approve mapping" instead of the
  terser "PASSED" block. The already-existing "APPROVED" state (after
  the operator actually clicks Verify) is untouched.

### Already existed (verified, left unchanged)

- The segmented mapping model, offset computation
  (`PageMapping.segments()`/`resolve()`), conflict detection
  (`conflicting_anchor_pairs()`), `MappingService.validate()`/`approve()`,
  and `suggest_next_anchor()` — all reused as-is, not modified. The new
  panels only read their outputs.
- The Segments table's raw `Status` column text (`"confirmed"` /
  `"needs a second anchor"`) is byte-for-byte unchanged — it's asserted
  verbatim by the pre-existing
  `test_segments_table_reflects_confirmed_and_unconfirmed_segments`.
  All new actionable language lives in the new, separate guidance panel
  instead of being written into that cell.
- Verification Anchors, Segments, and Mapping Preview tables all remain,
  unmodified in columns/behavior.

### Discovered, not fixed here

- `suggest_next_anchor()`'s candidate pool goes empty (returns `None`)
  as soon as there is exactly one confirmed segment, because
  `PageMapping.resolve()` then extrapolates that segment's offset to
  every other page — including pages that might actually belong to a
  different offset region (e.g. a front-matter renumbering later in the
  book). That's an existing property of the mapping algorithm itself
  (out of scope here, per the sprint brief), not a UX gap; noting it in
  case Sprint 5 (Conflict Resolution) wants to surface that risk to the
  operator.

### Verified

- Full test suite: 115/115 passing (107 pre-existing + 8 new in
  `tests/test_alignment_screen.py`: suggested-next reason/next-action,
  empty-state guidance with and without an outline, completion guidance
  once everything resolves, segment guidance's bounded and open-ended
  ranges, guidance updating on row selection without a full re-render,
  and anchor-acceptance feedback with row highlighting).
- Real GUI, offscreen Qt platform, against the actual `MainWindow` (not
  a fake): registered the real `fixture_a_normal.pdf` fixture through
  the real `LibraryService`, approved a real 3-chapter outline through
  the real `OutlineService`, then drove the real `AlignmentScreen` with
  `QTest.mouseClick` and combo-box selection. Confirmed: a fresh book
  opens to the empty-state message; adding the first anchor produces
  acceptance feedback, an actionable segment-guidance message, and bold
  highlighting on the affected Segments/Mapping-Preview rows; the
  "Suggested Next" panel is structured with Reason/Next action; adding
  the second (agreeing) anchor confirms the segment and flips the status
  panel to the "all confirmed / all resolved / Next Step" completion
  guidance; clicking "Verify and approve mapping" still approves the
  mapping and shows APPROVED, unchanged. Run against an isolated scratch
  project — the real `data/` corpus was never touched.

---

## Sprint 5 — Workspace 3 (Conflict Resolution & Diagnostics) UX polish

Date: 2026-08-04

### Completed

- **Mapping Diagnostics panel**: a new summary (Confirmed Segments /
  Warnings / Blocking Issues counts) plus a selectable list of every
  non-passed `ValidationIssue`, replacing the operator's need to parse
  scattered inline messages. The existing inline CONFLICT/BLOCKING/PASSED
  text in the status panel is left in place (nothing removed — see
  "already existed" below), so nothing an operator already relies on
  disappeared.
- **Plain-language explanations**: each diagnostic code (`offset_conflict`,
  `segment_unconfirmed`, `two_anchors_required`, `offset_unresolved`,
  `uncovered_entry`, `invalid_anchor`, `index_mismatch`,
  `anchor_out_of_range`) now has a short human-readable label and a
  full-sentence explanation of *why* it's a problem, not just the raw
  code.
- **Suggested Action**: every diagnostic detail view shows the existing
  `SUGGESTED_ACTION` text (already used elsewhere on this screen),
  surfaced per-item instead of only inline in the status block.
- **Row highlighting + navigation on selection**: selecting a diagnostic
  bolds and selects/scrolls to the specific anchor row(s) in Verification
  Anchors, the specific row in Segments, and the specific row in Mapping
  Preview — cross-referenced from the *same* underlying data
  `MappingService.validate()` already iterates (`conflicting_anchor_pairs()`,
  `unconfirmed_anchors()`, the per-anchor and per-entry loops), in the
  same order, so each diagnostic entry lines up with the row it actually
  came from rather than being guessed from message text.
- **Better Approval Blocking**: `approve()`'s generic
  `"Mapping verification blocked: <message>"` dialog is now a structured
  "Approval Blocked" message with Reason / Action Required / Affected
  Section per blocking issue, built by re-running the same `validate()`
  call `MappingService.approve()` already used internally (mapping state
  is unchanged between the failed approve and this re-validate, so the
  blocking set is identical) — not by parsing the exception string. The
  original raw exception is preserved in the dialog's "Show Details"
  pane, so nothing already available was hidden.

### Already existed (verified, left unchanged)

- Conflict detection (`PageMapping.conflicting_anchor_pairs()`), the
  segmented offset model, `MappingService.validate()`/`approve()`, and
  `SUGGESTED_ACTION` — all called exactly as before; the new panel only
  reads their outputs.
- The inline `CONFLICT`/`BLOCKING`/`PASSED` text block in the main status
  panel (`self.status`) — kept verbatim, not replaced, as a lower-risk
  choice than deleting something operators may already rely on.
- Verification Anchors, Segments, and Mapping Preview tables — unchanged
  in columns/behavior; the diagnostics panel complements them rather
  than replacing them, per the sprint brief.

### Discovered, not fixed here

- Found and fixed *during this sprint* (not shipped): `QListWidget
  .clearSelection()` clears selection state but does not clear
  `currentItem()`. The diagnostics-selection handler originally read
  `currentItem()`, so deselecting a diagnostic left its row/anchor
  highlight stuck. Caught by
  `test_conflict_diagnostic_explains_itself_and_highlights_both_anchors`
  before it shipped; fixed by reading `selectedItems()` instead.
- Confirmed again (see Sprint 4's note): with exactly one confirmed
  segment, `PageMapping.resolve()` extrapolates its offset to every
  other printed page, so `uncovered_entry` never fires in that state —
  it only appears once there are *two* confirmed segments with
  different offsets and a gap between them. The new
  `test_approval_blocked_message_is_structured_...` test had to
  construct that two-segment-gap scenario deliberately to exercise the
  code path at all. Not a bug (algorithm untouched), but worth knowing
  for Sprint 6's visualization work.

### Verified

- Full test suite: 119/119 passing (115 pre-existing + 4 new in
  `tests/test_alignment_screen.py`: diagnostics summary counts, conflict
  explanation/highlight/clear-on-deselect, conflict-resolved-removes-
  diagnostic, and the structured Approval Blocked message).
- Real GUI, offscreen Qt platform, against the actual `MainWindow`:
  registered the real `fixture_a_normal.pdf` fixture, approved a real
  3-chapter outline, then in `AlignmentScreen` **constructed a genuine
  conflict through the real UI** — added a real anchor at printed page 3,
  then added a second real anchor at the same printed page with a
  disagreeing physical page (a real operator mistake), via
  `QTest.mouseClick` on the actual "Add verification anchor" button (not
  by hand-building a `PageMapping`). Confirmed: the conflict appears in
  the diagnostics panel with a plain-language explanation and the
  correct Suggested Action; both conflicting anchor rows are highlighted;
  clicking "Verify and approve mapping" is blocked and raises a
  structured Approval Blocked message (Reason/Action Required, original
  error preserved in details); removing the bad anchor through the real
  "Remove selected anchor" button makes the diagnostic disappear; adding
  a real second agreeing anchor and clicking Verify then approves
  successfully, unchanged. Run against an isolated scratch project — the
  real `data/` corpus was never touched.

---

## Sprint 6 — Workspace 3 (Verification Dashboard & Completion Experience)

Date: 2026-08-05

This is the final Workspace 3 UX sprint. Sprints 4 and 5 answered "what do
I do next?" and "why can't I continue?"; this sprint answers "where am I
in the overall verification process?" by adding a dashboard and a
workflow-progress readout on top of the diagnostics those two sprints
built. Once accepted, Workspace 3 is considered complete and frozen —
further changes require a genuine regression, not new ideas.

### Completed

- **Verification Dashboard** (`self.dashboard_summary`, in a new
  "Verification Status" `QGroupBox` at the top of the workspace):
  Verification Anchors, Confirmed Segments, Outline Entries (`X / Y`),
  Blocking Issues, and a Status line. Pre-approval, Status reads
  **READY FOR APPROVAL** (green) once `blocking_count == 0` — the exact
  same count `MappingService.approve()` itself would refuse to approve
  past — or **ACTION REQUIRED** (red) otherwise. Post-approval, the same
  label switches to a **Better Success State**: Book / Verified Segments
  / Outline Entries / **READY FOR EXTRACTION**, keyed off the existing
  `mapping.approved` flag. Every number is read from state Sprints 1–5
  already compute (`mapping.anchors`, `confirmed_segments()`,
  `resolved_count`/`total_entries`, and the diagnostics panel's own
  `blocking_count`) — nothing new is calculated.
- **Visual Workflow Progress** (`self.workflow_summary`, in a new
  "Verification Workflow" `QGroupBox` beside the dashboard): a six-line
  ✓/□ checklist — Outline Approved, Anchors Added, Segments Confirmed,
  Outline Fully Resolved, Diagnostics Clear, Mapping Approved. Each line
  is a direct boolean read of existing state (outline approval via
  `OutlineService.approval()`, the rest identical to the dashboard's
  inputs); "Mapping Approved" flips to ✓ only after a real approval.
  Presentation only — no new workflow logic, no gating.
- **Segment Overview polish**: Segments-table rows now get a subtle
  status icon (`SP_DialogApplyButton` for confirmed, `SP_MessageBoxWarning`
  for unconfirmed) on column 0, and confirmed rows get the same light-green
  tint (`RESOLUTION_COLORS["segment"]`, already used elsewhere on this
  screen) that unconfirmed rows already got in amber — so both states are
  now visually grouped, not just the unconfirmed one. The `Status` column's
  raw text (`"confirmed"` / `"needs a second anchor"`) is untouched byte-
  for-byte — icons and backgrounds are attached to `QTableWidgetItem`
  separately from `.text()`, so the existing exact-match test keeps passing
  unmodified.
- **Approval Readiness**: covered by the dashboard's Status line above —
  operators see READY FOR APPROVAL / ACTION REQUIRED without needing to
  read or count diagnostics themselves.
- **Better Success State**: covered by the dashboard's post-approval
  content above (Book / Verified Segments / Outline Entries / READY FOR
  EXTRACTION), matching the sprint brief's example verbatim.

### Already existed (verified, left unchanged)

- The segmented mapping model, offset computation, conflict detection,
  `MappingService.validate()`/`approve()`/`suggest_next_anchor()` — none
  of it was touched; the dashboard and workflow panels only read outputs
  already produced by Sprints 1–5's code.
- The existing `self.status` guidance text (empty-state, segment
  guidance, anchor-acceptance feedback, diagnostics panel, mapping
  preview, all three tables) — all preserved exactly as-is. The dashboard
  and workflow panels sit above them as a new, additional summary; they
  do not replace or duplicate any existing message.
- The Segments table's `Status` column text and its 5-column schema —
  unchanged; only column 0's icon/background were extended.

### Existing functionality discovered

- `blocking_count` (already computed once per render for the Mapping
  Diagnostics panel added in Sprint 5) already includes conflicts as well
  as ordinary blocking issues, so it is exactly the same predicate
  `MappingService.approve()` uses to decide whether it will raise — no
  new "is this approvable" logic had to be written; the dashboard's
  Status line just reads that existing count.
- `OutlineService.approval(book_id)` was not previously read anywhere on
  this screen (Workspace 3 only ever read the mapping, not outline
  approval state) — needed for the workflow checklist's "Outline
  Approved" line, read-only, no new writes.
- Confirmed segment rows had no distinguishing background at all before
  this sprint; only unconfirmed rows were tinted (amber). Reusing the
  existing `RESOLUTION_COLORS["segment"]` constant (already used for the
  Mapping Preview's resolved cells) closed that gap without inventing a
  new color.

### Verified

- Full test suite: 124/124 passing (119 pre-existing + 5 new in
  `tests/test_alignment_screen.py`: dashboard ACTION REQUIRED before
  verification completes, dashboard READY FOR APPROVAL once everything
  resolves, dashboard's post-approval success summary, the six-step
  workflow checklist across its full lifecycle including a real
  `OutlineService.approve()` call and a real `screen.approve()` call, and
  the Segments table's confirmed/unconfirmed icon and background
  distinction).
- Real GUI, offscreen Qt platform, against the actual `MainWindow` (not a
  fake): registered the real `fixture_a_normal.pdf` fixture through the
  real `LibraryService.add()`, selected it via the real
  `MainWindow.set_book()`, saved a real 3-chapter outline through the
  real `OutlineService`, then drove the real `AlignmentScreen` with
  `QTest.mouseClick` on its actual "Add verification anchor" / "Remove
  selected anchor" / "Verify and approve mapping" buttons. Walked all
  five required states end-to-end and asserted the dashboard/workflow
  text at each: (1) fresh book — no outline approval, no anchors, ACTION
  REQUIRED, all workflow steps unchecked; (1b) outline approved, still
  zero anchors — Outline Approved flips to ✓; (2) partially verified —
  one anchor added, Anchors Added ✓ but Segments Confirmed still □,
  ACTION REQUIRED persists; (3) blocking diagnostics — a genuine
  conflicting anchor added at the same printed page through the real UI,
  dashboard stays ACTION REQUIRED with a nonzero Blocking Issues count,
  Diagnostics Clear stays □, the conflict appears in the existing
  diagnostics list; (4) ready for approval — conflict removed, two more
  agreeing anchors added, dashboard flips to READY FOR APPROVAL with
  Blocking Issues at 0, all workflow steps but Mapping Approved show ✓,
  and the confirmed segment row carries its new status icon; (5)
  approved — clicking the real Verify button flips the dashboard to the
  Mapping Approved / Book / Verified Segments / Outline Entries / READY
  FOR EXTRACTION success summary, Mapping Approved flips to ✓, and the
  pre-existing `self.status` panel still shows its own unchanged
  APPROVED text alongside it. Run against an isolated scratch project
  (`BOOKCORPUSBUILDER_CONFIG` pointed at a temp directory) — the real
  `data/` corpus was never touched.

### Risks

- None identified against the frozen mapping engine, schema, or approval
  logic — this sprint only adds two new read-only `QLabel`s and icon/
  background attributes on existing table items.

### Recommended next sprint

- Sprint 7 — Structure Builder (Workspace 2): Outline Editing UX, per the
  original roadmap. Workspace 3 should not be revisited unless a genuine
  regression is found.

---

## Sprint 7 — Workspace 2 (Structure Builder: Outline Editing Experience)

Date: 2026-08-05

Strictly scoped to editing the canonical outline table on the "B. Review
Outline" tab of `StructureBuilder`. Parser, JSON schema, provenance model,
approval logic, and merge algorithm were not touched — only read from.

### Completed

- **Editing toolbar reorganisation**: the single flat "Edit" `QGroupBox`
  (Best Fit / Add / Delete / Duplicate / Move Up / Move Down / Sort in one
  row) is now two clearly labeled groups — **Row Operations** (Add,
  Duplicate, Delete, Move Up, Move Down) and **Structure** (Sort) — with
  Best Fit Columns kept as its own small row above them. The pre-existing
  "Save and continue" group (Save Draft / Approve Outline / Copy CSV /
  Copy text) was left exactly where it was; Section 8 of the brief asked
  for the approval workflow to remain unchanged, and physically relocating
  Save/Approve into a new box would have been redesign, not reorganisation.
- **Row duplication**: already existed (`duplicate_row()`, preserving
  title/kind/level/page fields via `asdict`) — see "Existing functionality
  discovered" below. Added the missing selection/edit behavior: the
  operator now lands on the new duplicate (not the original) with its
  title field opened for immediate editing, mirroring `add_row()`'s
  existing pattern instead of inventing a new one.
- **Selection behaviour**: `delete_row()` now selects the row that
  logically takes the deleted row's place (or the new last row, if the
  last row was deleted) instead of leaving the table with no selection.
  `duplicate_row()` now selects the new row (see above). `add_row()` and
  `move()` already did this correctly and were left untouched.
- **Editing feedback (approval invalidation)**: `invalidate_approval()` —
  already called by delete/duplicate/move/sort — now shows "Outline
  modified. Approval has been cleared — review changes and approve
  again." on the status bar when it actually revokes an approval.
  `outline_edited()`'s own inline revoke-and-message block was replaced
  with a call to this same helper (removing duplicated logic, not adding
  new behavior) so every edit path now gives identical, positively-framed
  feedback instead of only cell edits explaining themselves.
- **Editing Status summary**: a small "Entries N · Modified YES/NO ·
  Approved YES/NO" line above the review table. `Entries` is
  `len(self.entries())`; `Approved` is the existing `OutlineService
  .approval().approved` flag already read elsewhere on this screen;
  `Modified` reuses the existing, already-persisted `edited_by_user`
  field (set by `add_row`/`duplicate_row`/manual cell edits) rather than
  inventing a new dirty-tracking flag. Refreshed from the single existing
  `validate()` call path plus `invalidate_approval()`, not sprinkled
  across every mutating method.
- **Empty-state guidance**: the "no outline yet" message (shown only once
  a book is selected but before any outline exists) now has an explicit
  "Next Step" pointing at the real, already-existing path — the
  "A. Create Structure" tab or the "Add from another source" button —
  instead of a single descriptive sentence with no call to action. The
  separate "no book selected" message and the tab-A "parse preview" empty
  state were left untouched.
- **Row-movement discoverability**: `Alt+Up` / `Alt+Down` / `Delete` were
  already wired as `QShortcut`s in this same file — but only on the
  Tab A candidate-preview table, not on the canonical outline table Tab B
  editing actually happens on. Mirrored the identical convention
  (same key sequences, same target actions) onto `self.table`, closing a
  real discoverability gap using an established pattern rather than
  adding drag-and-drop (which never existed here) or a new binding style.

### Already existed (verified, left unchanged)

- `duplicate_row()`'s field preservation (title, kind, hierarchy level,
  printed/physical/PDF-index page fields) — fully satisfied the brief's
  "Row Duplication" requirement already; only its selection behavior
  needed closing.
- `move()`'s selection-follows-the-row behavior — already correct.
- The outline parser, `OutlineService.validate()/approve()/revoke()`,
  the merge algorithm and its preview dialog, JSON/CSV import, Ollama
  candidate generation, and the "A. Create Structure" tab — untouched,
  called exactly as before.
- Page mapping, extraction, and Workspaces 1/3/4/5/6/7 — untouched.

### Behaviour intentionally left unchanged

- **No Promote/Demote buttons were added.** The brief's illustrative
  toolbar mockup for Section 1 showed a "Structure" group containing
  Promote/Demote, but those controls do not exist anywhere in the current
  code — only a directly-editable numeric "Level" column. Section 1's
  operative instruction is to "reorganize the **existing** controls," and
  the brief separately warns against inventing capabilities beyond what
  was asked. Adding new increment/decrement buttons over the `level`
  field would have been a new (if small) capability, not a
  reorganisation, so it was left out. The "Structure" group currently
  contains only the pre-existing "Sort" button. If literal Promote/Demote
  buttons are wanted, that's a small, explicit follow-up — flagged here
  rather than guessed at.
- `sort_printed()`'s selection is still not restored after sorting. The
  brief's Selection Behaviour requirement (#5) names exactly four
  operations — "insert, duplicate, move, delete" — and sort is not among
  them, so it was left as-is rather than expanding scope to an operation
  the brief didn't list.
- The "Save and continue" group's physical position/contents (Save Draft,
  Approve Outline, Copy CSV, Copy text) — unchanged, per Section 8.

### Existing functionality discovered

- `add_row()` was the one row-mutating method that did **not** call
  `invalidate_approval()` — duplicate/delete/move/sort all did, but a
  freshly added row on an approved outline previously left that approval
  standing. Fixed by adding the same call every sibling method already
  makes; this is a real pre-existing inconsistency the sprint's own
  "editing feedback" goal surfaced, not a new rule.
- The `Alt+Up`/`Alt+Down`/`Delete` keyboard-shortcut convention already
  existed in this exact file for the Tab A candidate table but had never
  been extended to the Tab B outline table — see "Row-movement
  discoverability" above.

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow` (not a
fake): registered the real `fixture_a_normal.pdf` fixture through the
real `LibraryService.add()`, selected it via `MainWindow.set_book()`, and
drove the real `StructureBuilder` with `QTest.mouseClick` on its actual
Parse Preview / Create new outline / Add / Duplicate / Delete / Move Up /
Move Down / Save Draft / Approve Outline buttons (`QMessageBox.question`
and `QInputDialog.getMultiLineText` mocked to auto-confirm, matching the
existing unit-test convention for these same modal dialogs — not a stand-in
for the screen under test). Exercised, in order: create outline from a
pasted TOC; insert a row (landed on and titled "New section" at the end);
duplicate a row (landed on the new duplicate, title/kind/page preserved,
original row after it left intact); delete a row (selection moved to the
correct next logical row); move a row down then back up via the real
buttons (selection followed each time); edit a title directly in the
table; approve via the real button and real `QInputDialog`; edit an
approved row and confirm the real status bar shows "Approval has been
cleared — review changes and approve again"; save via the real button and
re-load the draft from disk to confirm the edit persisted; approve again
successfully; and finally exercised the real `Alt+Up`/`Alt+Down`/`Delete`
keyboard shortcuts on the outline table with the window shown and
focused, confirming both row swaps and deletion. Also confirmed the
"Row Operations" and "Structure" group boxes exist and the "Save and
continue" group is untouched. Run against an isolated scratch project
(`BOOKCORPUSBUILDER_CONFIG` pointed at a temp directory) — the real
`data/` corpus was never touched.

### Test results

134/134 passing (124 pre-existing + 10 new in
`tests/test_structure_builder.py`: positive approval-invalidation
feedback message, duplicate-row field preservation and selection,
duplicate-invalidates-approval, delete-selects-next-logical-row,
delete-last-row-selects-new-last-row, move-keeps-selection,
add-row-invalidates-approval, the Editing Status summary across
entries/modified/approved transitions, the empty-state "Next Step"
guidance, and the mirrored `Alt+Up`/`Alt+Down`/`Delete` keyboard
shortcuts on the outline table).

### Risks

- None identified against the frozen parser, schema, provenance model,
  approval logic, or merge algorithm — every change in this sprint is
  either a selection/messaging addition around an existing mutating
  method, a read-only status label, or a widget regrouping.

### Recommended next sprint

- Sprint 8 — Structure Builder (Workspace 2): Taxonomy (chapter, appendix,
  preface, postscript, bibliography, etc.), per the user's stated
  separation of editing (Sprint 7) from semantic classification
  (Sprint 8). Once Sprint 8 is accepted, Workspace 2 should be considered
  complete and frozen, matching Workspace 3's precedent.

---

## Sprint 8 — Workspace 2 (Structure Builder: Semantic Classification)

Date: 2026-08-05

Strictly scoped to how the "Kind" (semantic type) of a canonical outline
entry is presented, edited, and explained on the "B. Review Outline" tab.
Parser, outline JSON schema, provenance model, approval logic, and
downstream extraction contract were not touched — only read from. The
brief reframed Sprint 8 from "Taxonomy" (implementation-oriented) to
"Semantic Classification" (operator-oriented): the real problem was an
operator not being able to confidently understand or correct an entry's
semantic role (e.g., a `kind` of `"postscript"`, which is not a supported
value, silently rendering as an opaque "unknown kind" warning).

### Completed

- **Controlled semantic editor**: the free-text Kind column (column 3) is
  now a `QComboBox` per row, populated from the real, existing
  `OutlineService.KINDS` set (`{part, chapter, section, subsection,
  analytical_section, preface, introduction, appendix, bibliography,
  notes, index, caption, other}`) with human-readable labels (`"analytical
  section"` → "Analytical Section", etc., computed generically — no
  hand-maintained label table to drift out of sync). No value outside
  `KINDS` can be *selected*; the underlying `QTableWidgetItem` for that
  column is kept (now non-editable by direct double-click) purely so
  `entries()`'s existing text-reading code keeps working unchanged —
  the combo is a presentation/interaction layer over the same cell, not
  a replacement data path.
- **Unknown-kind placeholder, never silently replaced**: a row whose
  stored `kind` is not in `KINDS` (e.g. `"postscript"`) gets one extra,
  clearly marked placeholder combo item ("⚠ postscript — needs review")
  *pre-selected*, echoing the real on-disk value back at the operator
  instead of silently defaulting to some other kind. Nothing is written
  back to the entry until the operator explicitly picks a different item
  — matching the brief's "advisory only, no automatic changes."
- **Semantic Status column**: a new, presentation-only 11th table column
  ("Semantic Status") showing "Classified" or "Review Needed" per row,
  with the same ✓ / ⚠ icon convention Sprint 6 already established for
  Workspace 3's Segments table (`SP_DialogApplyButton` /
  `SP_MessageBoxWarning`) — reused, not reinvented. Computed from the
  same `kind not in KINDS` predicate `OutlineService.validate()` already
  uses for its `unknown_kind` warning; not a new detection rule. This
  column is UI-only — never read by `entries()`, never serialized —
  exactly analogous to the pre-existing, non-schema "Resolution" column
  in Workspace 3's Mapping Preview.
- **Preserved original title**: verified by construction (the kind-change
  handler only ever calls `.setText()` on the Kind column's item, never
  the Title column's) and by a dedicated regression test and real-GUI
  scenario asserting the title stays byte-identical across a semantic
  reclassification.
- **Dry Review distinguishes Title from Semantic Type**: `unknown_kind`
  warnings are no longer rendered via the terse, generic
  `f"Section {sno} has unknown kind '{kind}'."` line. Structure Builder's
  own `validate()` (which already reformats `OutlineService.validate()`'s
  issues for display — a presentation-layer method, not the frozen
  service) now replaces that one line, per unclassified entry, with a
  labeled block:
  ```
  • Semantic type requires review
    Title: Postscript
    Current classification: postscript
    Recommended classification: Section
    Choose another semantic type from the Kind column if 'Section' isn't right.
    Code: unknown_kind
  ```
  `OutlineService.validate()` itself, and every other issue code's
  formatting, is untouched.
- **Semantic-specific editing feedback**: `invalidate_approval()` (added
  in Sprint 7) now takes an optional message override. `outline_edited()`
  passes a semantic-specific message — "Semantic classification updated.
  Outline approval has been cleared. Review and approve again." — only
  when the edited column is Kind; every other column (title, printed
  page, level, etc.) keeps Sprint 7's generic "Outline modified…"
  message. The underlying revoke call and guard condition are identical
  either way — only the displayed wording differs, per the brief's
  "reuse the existing approval invalidation... do not change approval
  logic."

### Already existed (verified, left unchanged)

- `KINDS`, `OutlineService.validate()`'s `unknown_kind` check, `approve()`
  /`revoke()` — called exactly as before; the combo and advisory text
  only read/reuse their outputs.
- The Kind column's role as the single source of truth for
  `entries()`'s `kind` field — unchanged; the combo writes back through
  the same `QTableWidgetItem.setText()` path any other cell edit uses.
- Sprint 7's `invalidate_approval()` revoke-and-message mechanism, the
  Editing Status summary, the Row Operations/Structure toolbar grouping,
  and the keyboard shortcuts — all untouched apart from
  `invalidate_approval()` gaining an optional parameter (backward
  compatible; every other caller still gets the original default
  message).

### Behaviour intentionally left unchanged

- **No new schema values were added.** The brief's illustrative selector
  mockup listed "Foreword" and "Postscript" as options, but neither is a
  member of the real `KINDS` set, and the brief's own bolded caveat says
  "Do not extend the schema unless it already supports additional
  values." The combo's *selectable* options are exactly `sorted(KINDS)`;
  an entry already holding `"postscript"` is surfaced via the unknown-kind
  placeholder (above) instead of being treated as a valid choice.
- **"Recommended classification" is a fixed value ("Section"), not
  inferred from the title.** The brief's example showed "Postscript" →
  "Chapter," but building any title-text-based recommendation would
  edge into the explicitly out-of-scope "automatic classification."
  `"section"` was chosen because it is `OutlineEntry`'s own existing
  schema-level default `kind` (`kind: str = "section"`, also the
  fallback `entries()` already uses when a Kind cell is blank) — reusing
  an existing constant rather than inventing a heuristic. This is a
  judgment call, flagged explicitly rather than guessed at silently.
- The outline parser, TOC/heading detection, JSON schema, provenance,
  merge algorithm, extraction, and Workspaces 1/3/4/5/6/7 — untouched.

### Existing functionality discovered

- A latent re-entrancy quirk in `outline_edited()`, present since before
  this sprint (Sprint 7 and earlier): the edited-metadata bookkeeping
  line (`title_item.setData(Qt.ItemDataRole.UserRole, metadata)`) itself
  emits `itemChanged` for the title column, synchronously re-entering
  `outline_edited()` for column 2 *before* the original call finishes.
  This was invisible in Sprint 7 because every column showed the same
  generic invalidation message regardless of order. Once Sprint 8 gave
  column 3 (Kind) its own, different message, the ordering became
  observable: the generic re-entrant call was winning the race and
  silently overwriting the semantic-specific message. Fixed by moving
  the invalidation call (which decides and shows the message) *before*
  the metadata bookkeeping in `outline_edited()`, so the intended message
  is always shown first and the re-entrant generic call becomes a
  harmless no-op (approval is already revoked by then). Caught by
  `test_changing_kind_on_an_approved_outline_shows_semantic_specific_feedback`
  before it shipped. The new Semantic Status column's own presentation-only
  updates are additionally wrapped in `blockSignals` so they never enter
  this signal chain at all.

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`: registered
the real `fixture_a_normal.pdf` fixture through `LibraryService.add()`,
saved a real 4-entry outline (chapter, appendix, bibliography, and an
unrecognized `"postscript"` kind — the exact scenario from the original
walkthrough) through the real `OutlineService`, then loaded it into the
real `StructureBuilder` via `load_draft()`. Confirmed: each row's combo
box is a genuine `QComboBox` preselecting the entry's real current kind;
Semantic Status reads "Classified" for the three recognized kinds and
"Review Needed" for the unrecognized one; every combo's valid options are
exactly the real `KINDS` set, with the postscript row's one placeholder
item correctly excluded from that check as the documented exception; the
Dry Review panel shows the structured "Title: Postscript / Current
classification: postscript / Recommended classification: Section" block
in place of the old one-line warning. Changed the Postscript row's kind
to "Chapter" via the real combo (`setCurrentIndex`, the standard
automated-testing equivalent of a user's dropdown selection) and
confirmed the title stayed exactly "Postscript" throughout. Approved the
outline via the real "Approve Outline" button and a mocked
`QInputDialog`, then changed another row's kind on the now-approved
outline and confirmed the status bar showed the semantic-specific message
verbatim, approval was revoked, and the row's title was untouched; saved
and re-approved successfully afterward. Finally confirmed a plain title
edit still shows Sprint 7's generic invalidation message, not the
semantic-specific one. Run against an isolated scratch project
(`BOOKCORPUSBUILDER_CONFIG` pointed at a temp directory) — the real
`data/` corpus was never touched.

### Test results

141/141 passing (134 pre-existing + 7 new in `tests/test_structure_builder.py`:
controlled-selector option set, unknown-kind placeholder and status,
known-kind "Classified" status, kind-change updates the entry without
touching the title, semantic-specific approval-invalidation feedback,
generic feedback still shown for non-Kind edits, and the Dry Review
title-vs-semantic-type advisory).

### Risks

- None identified against the frozen parser, schema, provenance, or
  approval logic. The one real risk this sprint carried — the message-
  ordering re-entrancy bug above — was caught by its own regression test
  before being reported as done, not discovered after the fact.

### Recommended next sprint

- This completes the planned Workspace 2 UX programme (Sprint 7:
  editing, Sprint 8: semantic classification). Per the same governance
  policy applied to Workspace 3 after Sprint 6, Workspace 2 is now
  presented for the project owner's explicit accept/freeze verdict
  rather than pre-emptively marked frozen here. If accepted, the next
  candidate is Workspace 1 (Library) per the roadmap discussed after
  Sprint 6 — "Stable, needs dashboard."

---

## Sprint 9 — Workspace 1 (Library: Project Cockpit)

Date: 2026-08-05

Following the project owner's acceptance of Sprint 8 and the formal
freeze of Workspace 2, the brief reframed Sprint 9 from "Library
Dashboard" to **Project Cockpit**: instead of merely prettifying the PDF
registry table, Workspace 1 should let the operator answer "where does
every book stand, and what's next?" without opening any other workspace.
Strictly scoped to `LibraryScreen`; registration, hashing, duplicate
detection, and every other workspace were not touched.

### Completed

- **Project Status column**: a new, presentation-only column showing one
  of `Registered` / `Outline Ready` / `Mapping Ready` / `Extracted` per
  book — the coarse pipeline stage, derived entirely from existing
  signals (outline approval, mapping approval, completed run history).
- **Next Action column**: a second new column giving the specific next
  step — `Create Structure` / `Approve Outline` / `Verify Mapping` /
  `Run Extraction` / `Browse Corpus` — computed by the same single
  `_lifecycle()` helper as Project Status, so the two columns (and the
  summary panel and double-click navigation, below) can never disagree
  with each other.
- **Book Summary panel**: a new "Book Summary" panel beside the table
  (table and panel live in a `QSplitter`, matching the multi-panel
  convention already used elsewhere in this app) showing, for the
  selected book: filename, registration date, Outline/Mapping status,
  completed-extraction count, latest run timestamp+status, a four-line
  Lifecycle badge checklist (✓/✗ Registered/Outline/Mapping/Extracted,
  reusing `AlignmentScreen`'s own `mark()` convention), a bold
  color-coded **Current Status** phrase, and **Next Action**.
- **Quick Navigation**: double-clicking a row now jumps straight to the
  workspace that book's current stage needs (Structure Builder → Page
  Alignment → Extract → Corpus Browser), reusing the exact
  navigate-and-preselect pattern `HistoryScreen.open_run()` and
  `ExtractScreen.open_in_browser()` already established — including
  preselecting the right run in Corpus Browser's `run_filter` when the
  target is the Browse stage.
- **Better empty-state guidance**: "No books registered." + an explicit
  "Next Step" pointing at the real "Add PDFs…" button, replacing the
  previous single descriptive sentence.
- **Cockpit auto-refresh**: `LibraryScreen.selection_changed()` (a
  no-op before this sprint) now calls the existing `refresh()`, so the
  table reflects an approval, mapping, or extraction made in another
  workspace as soon as the operator switches back to Library — without
  this, the whole "cockpit" premise would silently go stale.

### Already existed (verified, left unchanged)

- `LibraryService`, registration, hashing, duplicate detection, "Add
  PDFs…" / "Open PDF" / "Reveal" / "Hide from Library" — untouched and
  reverified working exactly as before (Scenario 7 of the real-GUI
  verification).
- The table's original 9 columns and their existing values (Filename,
  Size, Pages, Text, Draft, Mapping, Extraction, Last run) — unchanged,
  aside from the one deliberate "Approved" fix noted below.
- `OutlineService.approval()`, `MappingService.load()`,
  `HistoryService.records()` (already newest-first) — called exactly as
  before; every new column/panel only reads their outputs through one
  new, single `_lifecycle()` helper, no new persistence.

### Behaviour intentionally left unchanged

- No new database, cache, or persisted "project status" field — every
  value is recomputed live from the same three existing service calls
  each time `_lifecycle()` runs, per the brief's explicit "do not
  duplicate state / do not invent another database."
- No "Complete" tier beyond `Extracted`. The brief's own example listed
  five status words (`Registered → Outline Ready → Mapping Ready →
  Extracted → Complete`), but nothing in the existing data distinguishes
  a "Complete" state from "has at least one completed extraction" —
  inventing one (e.g., an "operator has reviewed this" flag) would be
  new persistence the brief explicitly forbids. `Extracted` is treated
  as the terminal status; flagged here rather than silently guessed at.

### Existing functionality discovered

- **The pre-existing "Approved" column was stale.** `OutlineService
  .revoke()` only flips a JSON flag — it never deletes the `_clean.csv`
  file — but the old column's value came from `clean.exists()`, so a
  book with a *revoked* approval still showed "Approved: Yes". Fixed by
  switching that column to the same `OutlineService.approval(book_id)
  .approved` flag the rest of the app already treats as authoritative
  (e.g., `AlignmentScreen`, `ExtractScreen`). Caught by
  `test_approved_column_reflects_real_approval_not_stale_clean_file`,
  which explicitly asserts the stale file is still on disk while the
  column correctly says "No".
- **`LibraryScreen.select_book_id()` re-selecting an unchanged row does
  not fire `itemSelectionChanged`.** Since `update_summary()` was
  originally only called from the selection-changed handler, refreshing
  the table after some *other* workspace changed a book's state (without
  that book's row index moving) left the new Book Summary panel showing
  stale data. Fixed by having `loaded()` call `update_summary()`
  unconditionally after any refresh, not only when Qt's own
  selection-changed signal happens to fire. Caught by the real-GUI
  verification script (unit tests hadn't exercised the
  refresh-without-reselection path) before being reported as done.

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`:
registered three real fixture PDFs
(`fixture_a_normal.pdf`/`fixture_b_frontmatter_offset.pdf`/
`fixture_c_scanned.pdf`) through the real `LibraryService.add()`.
Walked every required state on the real `LibraryScreen`: (1) empty
library — zero rows, empty-state guidance, placeholder summary; (2) one
freshly registered book — Registered/Create Structure, summary shows
"Not started", real double-click opens Structure Builder; (3) outline
approved via the real `OutlineService.approve()` — Outline
Ready/Verify Mapping, summary shows "Approved" and the ✓ Outline badge,
double-click opens Page Alignment; (4) mapping approved via the real
`MappingService.approve()` — Mapping Ready/Run Extraction, double-click
opens Extract; (5) a **real, synchronous `ExtractionService.run()`**
call (genuinely writing output files and a run-history record, not a
faked result) — Extracted/Browse Corpus, summary shows the extraction
count and "READY TO BROWSE", double-click opens Corpus Browser with the
completed run preselected in its `run_filter`; (6) three books in three
different lifecycle states simultaneously, each row independently
correct; (7) the real "Hide from Library" button (confirmation dialog
mocked, matching existing test convention) still removes a book from
the visible table without touching its underlying PDF file, proving
registration behavior is unmodified. Two real, non-cosmetic bugs were
found and fixed during this verification pass (the stale-selection
summary bug above, plus an offscreen-QTest double-click quirk that
turned out to be a test-harness artifact, not an app bug, confirmed by
a standalone repro). Run against an isolated scratch project
(`BOOKCORPUSBUILDER_CONFIG` pointed at a temp directory) — the real
`data/` corpus was never touched.

### Test results

157/157 passing (141 pre-existing + 16 new in `tests/test_library_screen.py`:
Project Status/Next Action for each of the five lifecycle stages, the
Approved-column staleness regression, the Book Summary panel's content
and lifecycle badges, double-click navigation for all four target
workspaces including the Corpus Browser run-preselect, the empty-state
guidance, the cockpit auto-refresh via `selection_changed()`, and
selection persisting across a refresh).

### Risks

- None identified against `LibraryService`, hashing, duplicate
  detection, or any other workspace's schema/logic. Both bugs found
  during this sprint's own verification were fixed and covered by a
  regression test before being reported as done, not left as known
  issues.

### Recommended next sprint

- Per the project owner's revised roadmap: Sprint 10 — Workspace 5
  (Corpus Browser), Reading Experience.

---

## Sprint 10 — Workspace 5 (Corpus Browser: Research Reading Experience)

Date: 2026-08-05

The brief reframed Sprint 10 from "Reading Experience" to "Research
Reading Experience": Corpus Browser is the operator's primary research
workspace now, not a technical inspection window. Strictly scoped to
`BrowserScreen`'s reading pane — search, filters, run selection,
auto-loading, and splitter persistence were explicitly preserved, not
touched. Extraction, corpus format, manifests, and every other workspace
were not touched.

### Completed

- **Reading Header**: `self.metadata` (previously a single dense line —
  `book_id · kind · printed N · physical N–N · run ID` plus a raw SHA-256
  line) is now a structured, labeled block: Book, Run (timestamp),
  Section, Printed Pages, Words, Kind, Physical Pages, Source Hash. Every
  fact the old line showed is still present — nothing was dropped, just
  relabeled and reorganized — plus two additions sourced from data
  already on the item/`RunRecord`: the book filename (`item["pdf"]`,
  already written into every JSONL record by the extraction pipeline)
  and the run's start timestamp (`RunRecord.started_at`, via the
  existing `format_timestamp()` helper).
- **Words count**: computed once per display as `len(text.split())`
  over the section's own `text` field, already fully loaded in memory
  for rendering — a derived display statistic, not a new persisted
  field (nothing added to the JSONL schema or manifests).
- **Better Reading Typography**: section text now renders as HTML
  paragraphs (`<p style="line-height:1.6; margin-bottom:1em">`) inside
  the same read-only `QTextEdit`, plus a 28px document margin and a
  slightly larger font. `setReadOnly(True)` is untouched — this is
  rendering for typography, not an editing capability, and "Copy text"
  (`toPlainText()`) still returns the exact original words unchanged.
- **Section Navigation + Previous/Next + Reading Status**: consolidated
  into one compact row (`◀ Previous Section` — status text — `Next
  Section ▶`) between the header and the text pane, rather than three
  separate widgets — the brief's own examples for these three
  requirements overlapped heavily (position-in-list, adjacent-section
  movement, and corpus/run status all describe "where am I" from
  different angles). The Previous/Next buttons call
  `self.results.setCurrentRow(...)`, reusing the exact existing
  `currentRowChanged → show_result` wiring — no duplicated loading
  logic — and disable correctly at the first/last row. The status text
  reports position within `self.items` (the *current* result set,
  filtered or not) and the selected run's real status, e.g. "Section 2
  of 3 · Run: Completed."
- **Reading Focus**: addressed as the cumulative effect of the above —
  a labeled header instead of a dense line, one compact nav/status row
  instead of clutter, and real typographic breathing room — rather than
  a separate mechanism (no pane was hidden, no splitter ratio changed;
  that would have been redesigning the workspace, which the brief
  explicitly forbade).

### Already existed (verified, left unchanged)

- **The three-tier empty-state system (Sprint 1) already fully satisfied
  requirement #6** ("no extraction exists" / "extraction exists but has
  no sections" / "filters returned no results") — `search()`'s existing
  branching was reused exactly as-is. Per the brief's own Engineering
  Guidance ("if an existing capability already satisfies part of the
  requirement, document it instead of rewriting it"), this was verified
  with three new regression tests rather than rewritten — no such tests
  existed before this sprint.
- `CorpusSearchService.search()`, `self.query`/`self.kind`/
  `self.run_filter`/`self.page_from`/`self.page_to`, `_run_selected()`
  and its `browser.last_run` persistence, `configure_splitter(...,
  "browser.results", ...)` and its debounced-save mechanism — all
  untouched, called exactly as before.
- Library → Browser (`LibraryScreen.open_relevant_workspace`, Sprint 9)
  and Run History → Browser (`HistoryScreen.open_in_browser`) navigation
  — both reused with zero changes and reverified end-to-end.

### Behaviour intentionally left unchanged

- **Section position ("N of M") reflects the current result set, not
  the corpus's total section count.** The brief's examples ("Section 12
  of 38") could be read either way; when a search/filter is active,
  "M" here is the filtered count, not the full run's section count.
  This was the more honest, lower-risk reading — reusing exactly
  `self.items`/`self.results` (Sprint 10's own "existing selection
  logic," per requirement #4) rather than adding a second, separate
  "total sections in this run" query that could disagree with what's
  actually on screen. Flagged explicitly rather than silently assumed.
- No drag-and-drop, no annotations, no AI summarization, no new search
  capability — all explicitly out of scope, confirmed absent.

### Existing functionality discovered

- None beyond what's noted above — this sprint's changes were
  additive/presentational and didn't surface any latent bugs in the
  reused Browser-loading or search code paths.

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`:
registered two real fixture PDFs, approved a real outline and mapping
for one of them, and ran the real `ExtractionService.run()` **twice**
(two genuine, separate extraction runs, each producing 3 real section
files) — the other book was left unextracted specifically for the empty
state. Walked every required scenario: (1) empty browser — a book with
no completed extraction shows the "No completed extractions yet"
message with results, status, and nav buttons all correctly cleared;
(2) extracted corpus / multiple sections — 3 real results, header shows
the real filename/section/word count; (3) Previous/Next — moved forward
through all 3 sections and back, confirming the header updates each
time and the buttons correctly disable at both ends; (4) existing
search — a real body-text phrase narrows the result set and the status
line honestly reports the *filtered* count, then clearing the query
restores all 3; (5) run switching — with two real completed runs on the
same book, the run filter lists both, and switching between them swaps
the displayed sections correctly; (6) Library → Browser — a real
double-click from Workspace 1 (Sprint 9's navigation) lands in the
Browser with sections and a preselected run; (7) Run History → Browser
— a real double-click on a specific run row lands in the Browser with
*that exact run* preselected; (8) splitter — confirmed the 3-pane
splitter and its layout controller are structurally intact under the
unchanged `"browser.results"` persistence key. One test-script-only
issue was found and fixed during this pass (a hardcoded search query
happened to also match unrelated front-matter text in this particular
fixture PDF — a property of the test fixture and a deliberately crude
test outline/mapping, not a Browser bug); the fix was to assert
behavior (filtering narrows results, status matches what's shown)
rather than an exact count tied to fixture content. Run against an
isolated scratch project (`BOOKCORPUSBUILDER_CONFIG` pointed at a temp
directory) — the real `data/` corpus was never touched.

### Test results

166/166 passing (157 pre-existing + 9 net new in
`tests/test_browser_screen.py`: the structured reading header's fields,
the word count, Copy-text fidelity after HTML rendering, Previous/Next
navigation with edge-disabling, the reading status's run-status text,
nav-status clearing on empty results, and the three pre-existing
empty-state messages now locked in by regression tests for the first
time. The file's `FakeWindow` gained a `history` service, since the new
reading header needs it — the two pre-existing tests were re-verified
passing unchanged with that addition.)

### Risks

- None identified against extraction, corpus format, manifests, or
  Browser's loading/search logic — every change is either a rendering
  change over already-loaded data or a thin wrapper around the existing
  `self.results.setCurrentRow()` selection path.

### Recommended next sprint

- Per the project owner's roadmap: Sprint 11 — Workspace 5 (Corpus
  Browser), Advanced Search and Retrieval — after which Workspace 5 can
  be considered for the same freeze verdict given to Workspaces 2 and 3.

---

## Sprint 11 — Workspace 5 (Corpus Browser: Research Retrieval)

Date: 2026-08-05

The brief reframed Sprint 11 from "Advanced Search" to "Research
Retrieval": not the search algorithm, but how the operator finds,
filters, navigates, and revisits results. Strictly scoped to
`BrowserScreen`'s retrieval UX. `CorpusSearchService`, indexing,
extraction, corpus schema, manifests, and every other workspace were
not touched. Sprint 10's Reading Header, typography, Previous/Next
Section, splitter, and metadata presentation were explicitly preserved.

### Completed

- **Search Summary** (#1) + **Better Filter Awareness** (#6),
  consolidated into one new panel (`self.search_summary`, above the
  results list) — the brief's own examples for these two requirements
  overlap (both describe result counts and active filters), so this
  avoids two near-duplicate widgets, matching Sprint 10's precedent for
  overlapping requirements. Shows: a result count, "Showing X of Y
  sections" when a specific run's real `RunRecord.written_count` is
  known and narrower than the full run (no new search call — "do not
  recompute search," per the brief), the active query text in quotes,
  the selected run's date, and a "Filter Active" flag shown only when a
  query/kind/page filter is actually set.
- **Clear Search** (#4): one new button resets query/kind/page-range
  filters to their defaults and calls the existing `search()` — no new
  filtering logic, a thin reset wrapper. Run selection is deliberately
  left untouched by Clear Search (which run you're browsing isn't a
  "search filter" to clear).

### Already existed (verified, left unchanged)

- **Search Context** (#2 — "Current Result: 5 of 18"): Sprint 10's
  `reading_status` already reports position within `self.items`, the
  *current, possibly filtered* result set (a design choice made and
  documented in Sprint 10's own report) — so it already reads "5 of 18"
  correctly once a search narrows the set to 18. No second, duplicate
  "Current Result" widget was added.
- **Previous Match / Next Match** (#3): given the above, Sprint 10's
  existing "◀ Previous Section" / "Next Section ▶" buttons already move
  strictly within the current filtered/matching result set — that *is*
  "the existing filtered list" the brief's own requirement #3 says to
  reuse. Adding a second, functionally identical pair of buttons next
  to them would have been pure UI duplication, contradicting the
  programme's own "reduce clutter" instinct (Sprint 10 §7). This overlap
  is flagged explicitly below rather than silently resolved either way.
- **Search State Preservation** (#5): `show_result()` and the
  Previous/Next handlers only ever call `self.results.setCurrentRow()`
  — neither has ever called `search()` — so selecting a different
  section already never clears the active query/filters. No test
  existed proving this before; one now does.
- **Search Empty State** (#7 — "no corpus" vs. "no search matches"):
  Sprint 1's three-tier empty-state system, already re-verified in
  Sprint 10, already differentiates exactly these cases. Nothing to add.
- `CorpusSearchService.search()`, `self.query`/`self.kind`/
  `self.run_filter`/`self.page_from`/`self.page_to`, `_run_selected()`,
  `configure_splitter(..., "browser.results", ...)` — untouched, called
  exactly as before.

### Behaviour intentionally left unchanged

- No new "Previous Match/Next Match" buttons were added — see above.
  If the project owner wants visually distinct controls even though
  they'd be functionally identical to Sprint 10's Previous/Next Section
  today, that's a naming/labeling follow-up, not new retrieval logic —
  flagged rather than guessed at.
- "Showing X of Y" only appears when a specific run is selected (a
  `RunRecord.written_count` exists) *and* it's larger than the current
  result count; under "All runs" or when nothing is filtered, only the
  plain "N matching section(s)" line is shown, since summing
  `written_count` across multiple runs risked double-counting and would
  have required new computation the brief explicitly forbade.
- No regex, fuzzy, or semantic search; no AI summarization; no
  annotations or bookmarks — all explicitly out of scope, confirmed
  absent.

### Existing functionality discovered

- None beyond the two "already satisfies the requirement" findings
  above (#2/#3 and #5/#7) — this sprint surfaced no latent bugs in the
  reused search/loading code paths.

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`:
registered two real fixture PDFs, approved a real outline and mapping,
and ran the real `ExtractionService.run()` twice (two genuine
completed runs, 3 real sections each). Walked all 10 required
scenarios: (1) empty corpus; (2) a normal search narrowing 3 real
sections down using an actual body-text phrase, with the summary
correctly showing the query, "Filter Active," and "Showing X of 3"
sourced from the real `RunRecord.written_count`; (3) a zero-result
search, distinguished from "no corpus"; (4) Previous Match/Next Match
— confirmed the existing Previous/Next Section buttons move strictly
within a 3-of-3 filtered set and disable correctly at its edges, with
the query still active throughout; (5) Clear Search restoring the full
3-section list and clearing the Filter Active flag; (6) search state
surviving a Previous/Next navigation click; (7) switching between two
real completed runs while a search stays active, correctly re-filtering
each run's own sections under the same query; (8) confirmed Sprint 10's
reading header, Previous/Next Section, and 3-pane splitter are all
still intact and behaving identically; (9) a real double-click from
Library (Sprint 9) into the Browser with a populated search summary;
(10) a real double-click from Run History onto a specific run, landing
in the Browser with exactly that run preselected and its real
`written_count` reflected in the summary. One test-script-only issue
was found and fixed during this pass (two hardcoded title-based queries
happened to also match an unrelated front-matter/TOC page in this
particular fixture, the same fixture-content artifact already noted in
Sprint 10 — not a Browser bug); fixed by querying real body text
instead. Run against an isolated scratch project
(`BOOKCORPUSBUILDER_CONFIG` pointed at a temp directory) — the real
`data/` corpus was never touched.

### Test results

173/173 passing (166 pre-existing + 7 net new in
`tests/test_browser_screen.py`: the search summary's count/query/run/
filter-active states including the "Showing X of Y" branch, Clear
Search, search state surviving section navigation, and Search Context
already matching the filtered set — the last two locking in existing
behavior with regression tests for the first time.)

### Risks

- None identified against `CorpusSearchService`, indexing, extraction,
  or any other workspace. Every change is either a new read-only
  summary label computed from already-available data, or a thin filter-
  reset wrapper around the existing `search()` call.

### Recommended next sprint

- Per the project owner's roadmap, Sprint 11 completes the planned
  Workspace 5 programme (Sprint 10: reading experience, Sprint 11:
  retrieval). As with Workspaces 2 and 3, the freeze verdict is left to
  the project owner rather than pre-emptively marked here. If accepted,
  the roadmap's next focus areas are Workspace 7 (Settings) and the
  cross-cutting items (Shared Task Lifecycle, Keyboard Workflow, Error
  Reporting, Documentation, Visual Consistency, Release Hardening).

---

## Sprint 12 — Workspace 7 (Settings & Configuration Experience)

Date: 2026-08-05

The project owner designated this the **last workspace-centric sprint**
— Workspaces 4 and 6 are left mature-but-unfrozen (no regression, no
reopening), and everything after this becomes cross-cutting,
application-wide work. Strictly scoped to `SettingsScreen`.
`SettingsService`, `AppSettings`' serialization/storage, path
resolution (`paths.py`), and application startup/initialization were
not touched — only read from.

### Completed

- **Logical grouping** (#1): the single flat `QFormLayout` (9 fields in
  one continuous list) is now four `QGroupBox` sections — **Project**
  (the 4 real path fields), **Parsing & Detection** (TOC/Index scan
  pages), **Extraction Defaults** (minimum characters, PDF viewer
  command), **Diagnostics** (OCR status). Built from the real,
  existing 9 `AppSettings` fields only — no new setting was invented
  (see "Behaviour intentionally left unchanged").
- **Operator-language descriptions** (#2): every one of the 9 fields
  now has a one-line, plain-language explanation underneath it (e.g.
  "Where extracted corpus files ... will be written" instead of just
  the label "Output Dir").
- **Path validation feedback** (#3): each of the 4 path fields
  (Project Root, Library Folder, Outline Directory, Output Directory)
  now shows a live status — `✓ Valid`, `⚠ Directory not found`,
  `⚠ Not a directory`, `⚠ Not writable`, or `Not set` for a blank
  field — updated on every keystroke (`textChanged`) and after
  "Choose…", with **no path-validation mechanism found anywhere else
  in the app to reuse** (see "Existing functionality discovered" — this
  is new, but strictly read-only filesystem inspection for display,
  never touching what gets saved or how the app starts).
- **Configuration Summary** (#4): one panel showing all 4 path fields'
  Configured/Needs Attention state plus an overall READY/ACTION
  REQUIRED status line, reusing the exact same per-path check computed
  for #3 — nothing validated twice. Deliberately covers all 4 real path
  fields rather than only the 3 named in the brief's illustrative
  example, since Outline Directory is exactly as required for the app
  to function as the other three (flagged explicitly).
- **Better empty-state guidance** (#5): a "Configuration Required"
  banner appears above the form, naming the specific field(s) that need
  attention, whenever the Configuration Summary isn't READY — replacing
  what was previously no guidance at all (an operator with a bad path
  had no indication anything was wrong until something else, elsewhere
  in the app, failed).

### Already existed (verified, left unchanged)

- `SettingsService.load()/save()`, `AppSettings`' field defaults and
  JSON serialization, `paths.py`'s canonical defaults, and
  `MainWindow`/`Services.rebuild()`'s startup sequence — all untouched,
  called exactly as before. `save()`'s body is byte-for-byte the same
  as before this sprint.
- The `self.fields` dict (keyed by the same 9 `AppSettings` field
  names) and the `choose_folder()` file-picker — reused as the single
  source of truth for both the grouped layout and validation; nothing
  parallel or duplicated.

### Behaviour intentionally left unchanged

- **No new settings were added.** The brief's illustrative grouping
  example named "Appearance: Theme, Font Size," "Behaviour: Auto
  Refresh, Confirmation Prompts," and "Diagnostics: Logs, Debug
  Information" — none of these fields exist anywhere in `AppSettings`.
  Per the brief's own instruction ("Do not invent new settings. Only
  improve organization"), the four real groups above were built from
  the 9 fields that actually exist, not the illustrative category names.
  Flagged explicitly rather than silently adding placeholder settings
  to make the example match.
- **No "Restore Defaults" mechanism was added.** Per requirement #6's
  own explicit instruction ("If none exists, document that fact...
  rather than implementing one") — none exists anywhere in
  `SettingsService`/`AppSettings`/`SettingsScreen`, so none was built.
  An operator can still manually restore individual defaults (they're
  visible in `paths.py`), but there is no one-click reset.
- Library, Structure Builder, Page Alignment, Extract, Browser, Run
  History — untouched.

### Existing functionality discovered

- **`input_pdf_dir`, `outline_dir`, and `output_dir` already
  self-heal on every startup.** `LibraryService`, `OutlineService`, and
  `HistoryService` each call `mkdir(parents=True, exist_ok=True)` on
  their respective directory in their own constructors, all invoked by
  `Services.rebuild()` during `MainWindow.__init__` — *before* Settings
  is ever shown. So by the time an operator can see a "Directory not
  found" warning for those three fields, the directory has usually
  already been created. `project_root` is the one field no service
  ever touches, so it's the only one that can genuinely stay missing —
  confirmed directly in real-GUI verification (Scenario 1) and reflected
  in the report rather than silently working around it.
- No other latent bugs were found; the pre-existing `save()`/`load()`
  round-trip behaved exactly as expected throughout.

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`: (1)
first launch — a scratch config with `project_root` pointing at a
folder that was never created, confirming it alone shows the warning
(the other three self-heal, per the discovery above), the Configuration
Summary shows ACTION REQUIRED, and the banner correctly names "Project
Root"; (2) path browsing — used the real "Choose…" dialog (mocked at
the `QFileDialog` boundary, matching this file's existing test
convention) to point all four fields at real, freshly created scratch
directories, confirming validation updates live with no save required;
(3) valid configuration — Summary flips to READY and the banner hides;
(4) invalid path (a real file where a directory was expected) and
missing path (a real nonexistent directory), each producing its own
distinct warning and pulling the summary back to ACTION REQUIRED, then
recovering once fixed; (5) configuration persistence — saved real
non-path settings (`minimum_chars`, `toc_scan_pages`,
`pdf_viewer_command`) via the real "Save local settings" button,
confirmed the real `LibraryService` was rebuilt against the newly
configured folder, then **constructed a second, brand-new `MainWindow`
instance** (a genuine restart simulation, not a reload of the same
object) and confirmed every saved value reloaded correctly and
validation still showed READY. Finally confirmed application behavior
is otherwise unchanged: a real PDF registered successfully through the
reconfigured Library folder on the restarted instance and landed in the
correct real directory on disk. Run against an isolated scratch project
(`BOOKCORPUSBUILDER_CONFIG` pointed at a temp directory) — the real
`data/` corpus was never touched.

### Test results

184/184 passing (173 pre-existing + 11 new in the new
`tests/test_settings_screen.py`: grouped sections, operator-language
descriptions, all four path-status states (`✓ Valid` / not found / not
a directory / not writable / not set), live validation on edit, live
validation after "Choose…", and save/load round-tripping every field
unchanged).

### Risks

- None identified against configuration storage, serialization,
  startup, or path resolution — every change is either a read-only
  filesystem status check used purely for display, or a widget
  regrouping. The one new "logic" (path status inspection) never
  affects what's saved or how the app behaves, only what's shown.

### Recommended next sprint

- This completes the planned workspace-maturation programme (Workspaces
  1/2/3/5/7 frozen or freeze-eligible; 4 and 6 mature and intentionally
  left alone). Per the project owner's roadmap, the next candidate is
  Sprint 13 — Shared Task Lifecycle, the first of the cross-cutting,
  application-wide sprints (common progress, cancellation, failure
  handling, and task completion presentation across every workspace
  that runs a background task).

---

## Sprint 13 — Product Refinement: Shared Task Lifecycle

Date: 2026-08-05

The first cross-cutting sprint — not tied to one workspace. Scoped
entirely to `MainWindow.run_task()` / `FunctionWorker`, the one shared
background-task mechanism every workspace uses, plus the minimal,
targeted opt-in wiring needed in the one screen with a real, demonstrated
defect. No business logic (extraction, mapping, parsing) was touched.

### Task lifecycle inventory (required "before making changes" audit)

Every real `run_task()` call site in the active app (an `OutlineScreen`
class defined in `main_window.py` has two more calls but is dead code —
never instantiated or added to `MainWindow.screens`, confirmed by
grepping for any other reference to it — so it's excluded below):

| Call site | Workspace | `with_progress` | Visible "in progress" UI to reset on failure? |
|---|---|---|---|
| `LibraryScreen` "Refresh" button | WS1 (frozen) | No | No |
| `LibraryScreen.select()` (page-count inspection) | WS1 (frozen) | No | No |
| `StructureBuilder.detect_from_pdf()` | WS2 (frozen) | No | No |
| `StructureBuilder.generate_with_ollama()` | WS2 (frozen) | No | No (transient status-bar message only) |
| `ExtractScreen.start()` | WS4 (mature) | **Yes** | **Yes** — Extract/Cancel buttons, progress bar, checklist |

Only `ExtractScreen.start()` has visible, persistent "in progress" UI
state that a failure could leave stranded — confirmed by inspecting each
of the other four call sites' surrounding code, none of which disables a
button, shows a progress bar, or otherwise visibly commits to a "running"
state the operator could see get stuck.

**The Sprint 3 finding, confirmed and now understood precisely:**
`ExtractionService.run()` (`services/extraction.py`) already catches its
own internal exceptions, builds a proper `"failed"`-status `RunRecord`,
and saves it to run history (line ~133) — but then **deliberately
re-raises** (`raise RuntimeError(error)`, line ~135) instead of returning
that record. That re-raise is what actually reaches `FunctionWorker`,
which sends it down `worker.failed` instead of `worker.finished` —
meaning `ExtractScreen.completed()`'s own `"failed"` branch (which
already existed, already handled `record.status == "failed"` correctly)
was **unreachable dead code**: the generic error dialog was the only
thing that ever fired, and the screen's own progress bar, checklist, and
Cancel button were left exactly as they were mid-run, forever, until the
operator navigated away.

**Cancellation** exists in exactly one place: `ExtractScreen`'s
`Event`-based `cancel_event` / "Cancel" button. Nowhere else in the app
has any cancellation mechanism — documented per requirement #5's explicit
instruction, not invented for the other four call sites.

### Completed

- **Centralized failure-path fix** (the Sprint 3 deferred issue):
  `run_task()` gained an optional `on_failure(message, details)`
  parameter. When a task fails, `on_failure` — if supplied — is now
  called *in addition to* (not instead of) the existing generic error
  dialog, letting a workspace reset its own in-progress state instead of
  leaving it stranded. Wired up in exactly the one place with a real,
  demonstrated bug: `ExtractScreen.start()` now passes
  `on_failure=self.failed`, and a new `failed()` method resets the
  Cancel button, sets `progress_state` to `"✗ Task Failed"`, and
  populates the Completion Summary with a **Task Failed / Reason / What
  you can do** panel — mirroring `completed()`'s existing structure for
  the success case (requirement #4's "presentation should be shared").
  Every other call site is unaffected (`on_failure` defaults to `None`
  and is fully backward compatible — confirmed by a dedicated test).
- **Consistent failure presentation, centralized once**: the generic
  dialog every `run_task()` failure already produced now reads **"Task
  Failed" / Reason / What you can do**, built once inside `run_task()`
  itself — every current and future caller gets this automatically,
  with zero changes needed in any individual workspace file (Engineering
  Guidance #3: "if a problem can be solved once in run_task(), do not
  patch six workspaces individually"). The traceback is still preserved
  in the dialog's existing "Show Details" pane, unsuppressed
  (requirement #3's explicit instruction).
- **Task recovery information, reusing a real existing guarantee**:
  `ExtractScreen.failed()`'s message states "Nothing was written to your
  output folder" — this is not a new promise, it's `ExtractionService
  .run()`'s existing temp-directory-then-atomic-`os.replace()` pattern
  (already there, unmodified), simply surfaced to the operator instead
  of left implicit.
- **Shared, workspace-agnostic indeterminate progress indicator**
  (requirement #2, for the four call sites with `with_progress=False`
  and previously zero visible feedback of any kind): a new
  `self.task_indicator` label in `MainWindow`'s own shared header (not
  inside any workspace's layout) shows `"⏳ <task> running…"` for the
  duration of any task that doesn't have its own dedicated progress
  widget, and clears on completion or failure. Because it lives in
  shared chrome rather than inside `LibraryScreen`/`StructureBuilder`'s
  own widget trees, this required *zero* changes to either frozen
  workspace's own files to give their background tasks *some* visible
  running state for the first time.
- **`last_action` now updates on failure too** (previously success-only):
  `"Last action: <task> failed"`, using the exact same label already in
  the header — one more small, centralized, already-existing-mechanism
  reuse rather than new UI.
- **Shared vocabulary, minimal and targeted** (requirement #7 — "only
  remove obvious inconsistencies," not a rewrite): `ExtractScreen`'s
  initial progress-state label changed from `"Idle"` to `"Ready"`,
  matching the `READY`/`ACTION REQUIRED` vocabulary already established
  across Sprints 6, 9, and 12. This was the one clear, isolated
  inconsistency found; nothing else was renamed.

### Already existed (verified, left unchanged)

- `FunctionWorker`, the `QThread`/`moveToThread` plumbing, `self.threads`
  /`self.workers` bookkeeping and their `deleteLater()`-based cleanup —
  untouched.
- `ExtractionService.run()`, `dry_run()`/`preflight()`, the outline
  parser, page mapping, and every other business-logic module — not
  modified at all, only read.
- `ExtractScreen.completed()` — untouched; it still correctly handles
  the `"completed"` and `"cancelled"` statuses exactly as before (both
  arrive via the normal, working `worker.finished` path, since
  `ExtractionService.run()` only *raises* on the failed branch — the
  cancelled branch returns normally). Its dead `"failed"` branch was
  deliberately left in place rather than deleted, since it's harmless,
  low-risk, and removing it wasn't necessary to fix the actual bug (the
  new `failed()` method now handles that case instead, via the path that
  actually fires).
- Page Alignment's `approve()` (mapping approval) is a synchronous call,
  not a `run_task()` consumer at all — confirmed directly (WS3 is
  frozen; re-verified functionally unchanged in real-GUI verification,
  Scenario 2).

### Behaviour intentionally left unchanged

- **`LibraryScreen` and `StructureBuilder`'s `run_task()` call sites were
  not given `on_failure` hooks.** Both workspaces are frozen. Neither has
  any visible "in progress" UI state to strand on a failure (per the
  inventory table above) — there is no demonstrated regression to fix
  there, only a theoretical one, and Engineering Guidance #4/#5
  explicitly forbid reopening a frozen workspace for anything short of a
  real bug. They do now get the shared header's indeterminate indicator
  "for free" (a purely infrastructural, non-workspace change) and the
  improved generic failure dialog — both apply automatically without
  touching either file.
- **No new task framework, state machine, or job queue.** "READY /
  RUNNING / COMPLETED / FAILED / CANCELLED" (#1) is expressed entirely
  through existing widgets and existing signals (`worker.finished`
  /`worker.failed`, button `.setEnabled()`, label text) — there is no new
  `TaskState` class or enum anywhere.
- **No cancellation was added anywhere it didn't already exist.** Per
  requirement #5's explicit instruction — documented above, not invented.
- **Vocabulary was not rewritten wholesale.** Only `"Idle"` → `"Ready"`
  changed; every other status string across the app (Library's `Project
  Status` column, Settings' `READY`/`ACTION REQUIRED`, run-history's raw
  `completed`/`running`/`failed`/`cancelled`, etc.) was left exactly as
  each accepted sprint left it, per requirement #7's "do not rewrite
  every message."

### Existing functionality discovered

- The precise mechanics of the Sprint 3 bug, above (the internal
  catch-then-reraise in `ExtractionService.run()` that made
  `ExtractScreen.completed()`'s own `"failed"` branch permanently
  unreachable) — confirmed by reading the exact source lines rather than
  assumed from Sprint 3's summary.
- `ExtractionService.run()`'s existing temp-directory/atomic-promote
  transaction pattern, which makes "nothing was written on failure" an
  honest, verifiable claim rather than an assumption — confirmed in
  real-GUI verification by checking the real `runs/` directory's
  contents after a real failure.

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`, across
all required scenarios: (1) a real, successful structure build
(`detect_from_pdf()`, WS2/frozen) — confirmed the shared task indicator
now shows `"⏳ detect running…"` where it previously showed nothing at
all, clears on completion, and `last_action` updates; (2) a real,
successful page-mapping approval (WS3/frozen) — confirmed completely
unaffected (not a `run_task()` consumer); (3) a real, successful
extraction (WS4) — confirmed Extract's own dedicated progress bar is
used and the shared indicator correctly stays empty (no redundant,
competing indicator); (4) a **real extraction failure** — patched only
the `extraction` service instance's own `run` method to raise (not the
shared `BookRecord` class, which an earlier version of this verification
pass patched instead and crashed the interpreter via a cross-thread
race — a test-script bug, fixed by patching a single owned instance
method instead, not a finding about the app itself) — confirmed the
generic "Task Failed / Reason / What you can do" dialog fires with the
real exception message and a preserved traceback, `ExtractScreen.failed()`
resets the Cancel button and shows its own "Task Failed" panel including
"Nothing was written to your output folder," and confirmed by directly
inspecting the real `runs/` directory that no partial output was
promoted; (5) invalid input (starting extraction with no book selected)
— confirmed the existing, specific `"Extraction could not start"` guard
still fires before `run_task()` is ever reached, distinct from the new
generic "Task Failed" dialog; (6) repeated task execution — a fresh
`dry_run()` + `start()` after a real failure completes normally (not
stuck), and a second, repeated no-progress task shows the indicator
again correctly. Two real, non-cosmetic issues were found and fixed
during this verification pass itself, before reporting: patching a
shared dataclass's class-level property across threads is unsafe (fixed
by patching an owned instance method instead), and `MainWindow.run_task()`'s
generic `QMessageBox`-based failure dialog blocks on `.exec()` waiting for
a click — this script is the first to deliberately trigger a *real*
background-task failure against the real `MainWindow` (every earlier
sprint's real-GUI scripts only exercised success paths for real
background tasks), so this is the first time that blocking behavior was
actually exercised outside the FakeWindow-based unit tests; worked
around in the verification script the same way prior sprints already
handle `QMessageBox.question` (mocking the modal, not the app). Run
against an isolated scratch project (`BOOKCORPUSBUILDER_CONFIG` pointed
at a temp directory) — the real `data/` corpus was never touched.

### Test results

192/192 passing (184 pre-existing + 8 new: 3 in
`tests/test_extract_screen.py` — "Ready" vocabulary, a real triggered
extraction failure resetting the screen's stuck UI state end-to-end
including a real run-history record check, and a successful retry after
a real failure — plus 5 in the new `tests/test_task_lifecycle.py`,
which drives the real, threaded `MainWindow.run_task()` (not a
synchronous fake) to cover the centralized infrastructure directly:
`last_action`/indicator on success, the structured failure dialog with
preserved traceback, the `on_failure` hook firing, backward compatibility
for callers that don't pass it, and progress-reporting tasks correctly
not using the generic indicator. `tests/test_extract_screen.py`'s
`FakeWindow.run_task()` was extended to mirror the real
try/except/on_failure/show_error contract, matching this project's
existing convention of synchronous fakes for fast per-screen tests.
A pre-existing, unrelated `QThread` deleteLater-cleanup timing artifact
(cosmetic — a stderr warning, never a test failure) was also found while
stabilizing the new real-threaded tests under full-suite load; worked
around by draining the event loop a few extra turns after each
task-completion wait, which is how Qt itself expects `deleteLater()`
cleanup to be given a chance to run.

### Risks

- None identified against extraction, page mapping, the outline parser,
  or any workspace's business logic — every change is either additive to
  `run_task()`'s signature (backward compatible, defaults to `None`) or
  confined to `ExtractScreen`'s own new `failed()` method.
- The `QThread` deleteLater-cleanup timing artifact noted above is
  real but pre-existing and cosmetic (stderr noise at process/interpreter
  teardown, not a functional defect); it was not introduced by this
  sprint and was not in scope to fix (no workspace or business logic is
  affected), but is worth having on record for anyone else writing a
  real-threaded test or verification script against this app in future.

### Recommended next sprint

- Per the project owner's roadmap: Sprint 14 — Keyboard Workflow, the
  next cross-cutting, application-wide sprint.

---

## Sprint 14 — Product Refinement: Operator Navigation & Keyboard Workflow

Date: 2026-08-05

Deliberately reframed by the project owner from "Keyboard Workflow" (a
solution) to "Operator Navigation" (the problem), specifically to force a
full interaction-model audit before any change. That audit is reported in
full below, since it's the actual deliverable this sprint's brief asked
for ahead of any code change.

### Navigation audit (required "before making changes" deliverable)

**Existing keyboard shortcuts** — `QShortcut` exists in exactly one file,
`widgets/structure_builder.py` (Workspace 2): `Ctrl+S`→save_draft,
`Ctrl+Return`→parse_preview, and `Delete`/`Alt+Up`/`Alt+Down` scoped
separately to the candidate table and the canonical outline table (added
across Sprints 5–7). No other workspace has any `QShortcut` at all. No
duplicates or conflicts were found — each pair is scoped to a distinct
widget, so there's nothing colliding within the same context.

**Tab order** — no `setTabOrder()` call exists anywhere in the app; every
workspace relies entirely on Qt's implicit order (widget-construction
order within each layout). Spot-checked via real keyboard Tab/Shift+Tab
traversal (Settings' form) and found sane/predictable — matching each
screen's own top-to-bottom construction order, which already follows the
operator's natural reading order. No `setTabOrder()` calls were added,
since no actual anomaly was found to justify one.

**Default button behaviour** — the plain `QMessageBox.question(parent,
title, text)` convenience call, used at all 7 confirmation dialogs across
the app, defaults **Enter to "Yes"** (confirmed empirically, not assumed
— see "Existing functionality discovered"). For the two dialogs that
guard genuine, hard-to-undo data loss (Structure Builder's "Clear pasted
text?" and "Delete outline row?"), this means a reflexively-pressed Enter
key confirms the destructive action. The other five (an informational
JSON-import routing question, "Create new outline?", two "Revoke existing
approval?" questions, and "Hide from Library" — whose own message text
already says "will not be deleted... restores it") were judged safe or
reversible enough to leave unchanged, to avoid rewriting every dialog
when only two are genuinely destructive.

**Escape behaviour** — `QDialog`'s native Escape→reject() and
`QMessageBox`'s native Escape→No/Cancel are both stock Qt behaviour that
already worked correctly; confirmed directly against a real `QDialog` in
real-GUI verification rather than assumed.

**`QInputDialog`/`QMessageBox` Enter/Escape** — both are standard Qt
convenience dialogs; their default-button and Escape handling is native
Qt behaviour, not application code, and was confirmed working as-is.

**Accessibility (buddy labels)** — `QFormLayout.addRow(str, widget)`
**already auto-assigns the label as the field's buddy** (confirmed
empirically — a real, useful, previously-undocumented fact about this
codebase, which uses `form.addRow("Label", widget)` almost everywhere:
Settings, Extract, Alignment's anchor form, etc. all already have correct
buddy associations for free). The only labels *not* covered by this were
two bare `QLabel`s in Browser's filter row ("Printed from" / "to"),
added via a plain `QHBoxLayout` instead of a form — the one real,
low-risk accessibility gap found.

**Focus recovery after Add/Delete/Duplicate/Move** — Sprint 7 already
solved this correctly for `add_row()`/`duplicate_row()` (both call
`editItem()`, which grabs real keyboard focus into the new cell). But
empirically confirmed (via a real button click, not a pre-focused table)
that `delete_row()`/`move()` and Page Alignment's `remove_anchor()` only
called `selectRow()` — which changes the *visual selection* but does
**not** move keyboard input focus away from whatever button was just
clicked. A real operator who deletes/moves a row by mouse and then tries
to keep working by keyboard would need an extra, unexplained Tab press
first. This was the sprint's single most concrete, demonstrated finding.

**Workspace navigation** — `self.navigation` (the left-hand workspace
list) is a plain `QListWidget`; Qt's native Up/Down arrow-key handling
already moves the current row (and `currentRowChanged` already switches
workspaces) once it has focus — confirmed directly via real keyboard
input. No new global hotkeys were added (explicitly out of scope).

### Completed

- **Safe-by-default destructive confirmations**: new shared helper
  `confirm_destructive(parent, title, text)` in a new module,
  `gui/widgets/dialogs.py` — identical in appearance to the plain
  `QMessageBox.question()` call it replaces, except `No` is the default
  button. Applied to exactly the two genuinely destructive confirmations
  found in the audit (`clear_paste()`, `delete_row()`, both in Structure
  Builder). Every other `QMessageBox.question()` call in the app is
  untouched.
- **Focus recovery, closing the gap the audit found**: `setFocus()` added
  after the existing `selectRow()` calls in Structure Builder's
  `delete_row()`/`move()` and Page Alignment's `remove_anchor()` (which
  also gained the same select-the-next-logical-row restoration
  `delete_row()` already had, reusing that exact pattern). Confirmed via
  real GUI: focus now lands back on the table after a real button click,
  not stuck on the button.
- **Enter-to-submit on Page Alignment's anchor form** (requirement #2's
  own "Add Anchor ... → Add" example): `self.printed.lineEdit()
  .returnPressed` and `self.physical.lineEdit().returnPressed` both now
  call `add_anchor()`, matching the exact convention Corpus Browser's
  search field already established.
- **Buddy labels for Browser's page-range fields**: `"Printed from"` and
  `"to"` now have explicit `.setBuddy()` calls, closing the one
  accessibility gap the audit found.

### Already existed (verified, left unchanged)

- Every `QShortcut` in Structure Builder — unchanged, reused, reverified
  working after this sprint's other changes.
- `QFormLayout`'s automatic buddy assignment, `QDialog`'s native Escape
  handling, and Browser's existing `returnPressed`-to-search wiring — all
  confirmed already correct, none rewritten.
- Sprint 7's `add_row()`/`duplicate_row()` focus handling — confirmed
  already correct; the new `setFocus()` calls were added only where the
  audit found the gap (`delete_row()`, `move()`, `remove_anchor()`), not
  copied indiscriminately across every mutating method.

### Behaviour intentionally left unchanged

- **Five of the seven `QMessageBox.question()` confirmations were left
  at the plain, Yes-default convenience call**, not converted to
  `confirm_destructive()`. Only the two with genuine, hard-to-undo data
  loss were changed — converting all seven would have been "rewriting
  every message," which the brief's own Engineering Guidance for
  vocabulary changes explicitly warned against applying too broadly
  elsewhere in this programme, and the same restraint applies here.
- **No `setTabOrder()` calls were added anywhere.** The audit found tab
  order already sane; adding explicit calls with no demonstrated problem
  would have been exactly the kind of "shortcuts merely because they are
  common elsewhere" the brief explicitly forbade.
- **No global hotkeys, no Vim/Emacs modes, no new navigation
  framework.** Workspace switching already works by keyboard once the
  navigation list has focus — this was verified, not built.
- **Structure Builder and Page Alignment are formally frozen
  (`docs/GOVERNANCE.md` §7)**, yet both received small changes in this
  sprint (`confirm_destructive`, focus recovery, Enter-to-add). This is a
  deliberate reading of this sprint's own charter: every change made
  there is purely infrastructural/interaction-level (a dialog's default
  button, where keyboard focus lands, an additional key binding to an
  *existing* handler) — none alters layout, business logic, or what a
  mouse-driven operator sees or does. Flagged explicitly here rather than
  silently done, matching this whole programme's transparency
  convention; Workspace 1/4/5/6/7 (not formally frozen, per the same
  governance record) were touched with the same restraint but a lower
  bar of justification.

### Existing functionality discovered

- **The plain `QMessageBox.question()` call defaults Enter to "Yes,"**
  confirmed by direct empirical probing (constructing the exact same
  message box the app builds and simulating a real `QTest` Enter
  keypress) rather than assumed from Qt documentation, which was
  ambiguous on this specific point. This was the finding that justified
  requirement #2/#7's dialog-default work.
- **`QFormLayout.addRow(str, widget)` already auto-assigns buddy labels**
  — also confirmed empirically, not assumed. This substantially narrowed
  the real accessibility gap down to the two bare labels in Browser's
  filter row.
- **`selectRow()` does not move keyboard focus** — confirmed by
  simulating a real button click (not a pre-focused table) before
  reading this sprint's brief too literally; this is what turned
  requirement #5 from a vague instruction into a concrete, fixable bug.

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`, driving
genuine `QTest` keyboard events (not mocked focus/selection state) across
8 scenarios: (1) workspace switching via Up/Down arrows on the real
navigation list; (2) Tab and Shift+Tab traversal through Settings'
real form, confirming focus moves forward and (critically) back to the
exact same field; (3) Structure Builder's pre-existing `Ctrl+Return` and
`Alt+Down` shortcuts, reconfirmed unaffected; (4) the new safe-by-default
`Delete outline row?` confirmation — a simulated reflexive "No" leaves
the row in place, then an explicit "Yes" (via a real button click)
deletes it and returns focus to the table; (5) focus recovery after a
real "Move Down" button click; (6) a real Enter keypress in Page
Alignment's physical-page field adding a real anchor with no mouse click
at all, and focus correctly returning to the anchors table after a real
"Remove selected anchor" click; (7) a real `QDialog` closing on a real
Escape keypress; (8) Browser's pre-existing Enter-to-search convention,
reconfirmed unaffected. Two real issues were found and fixed in the
verification *script* itself during this pass (not the app): `QMessageBox
.question()` is a Shiboken-bound static method that execs its own message
box internally in C++, so patching `QMessageBox.exec` alone (sufficient
for Sprint 13's `show_error()`/`confirm_destructive()`, both of which
call `.exec()` directly in Python) did not intercept it — `.question()`
itself also had to be patched; and Structure Builder has two "Delete"
buttons (the candidate table's and the canonical table's) — `findChildren`
picked the invisible one from the wrong tab, exactly the same ambiguity
already discovered and fixed in an earlier sprint's Library verification,
here fixed by filtering on `.isVisible()`. A third finding turned out to
be a test-only artifact rather than a bug: delivering a synthetic Enter
keypress directly to a `QSpinBox`'s internal `.lineEdit()` fired
`returnPressed` twice, but targeting the spinbox itself (which forwards
to its internal line edit via Qt's normal focus-proxy routing, exactly
how a real operator's keystroke would arrive) fired it once — confirmed
by a standalone repro before concluding the production code was correct.
Run against an isolated scratch project (`BOOKCORPUSBUILDER_CONFIG`
pointed at a temp directory) — the real `data/` corpus was never touched.

### Test results

204/204 passing (192 pre-existing + 12 new: 3 in the new
`tests/test_dialogs.py` for `confirm_destructive()` itself; 4 in
`tests/test_structure_builder.py` (the new safe-default confirmation,
declining leaves the row in place, and focus recovery after Delete and
Move); 4 in `tests/test_alignment_screen.py` (Enter-to-add from both
page fields, and focus/selection recovery after removing an anchor,
including the last-anchor edge case); 1 in `tests/test_browser_screen.py`
for the new buddy-label association). Two pre-existing tests
(`test_structure_builder.py`'s two `delete_row` tests and its keyboard-
shortcut test) were updated to mock the new `confirm_destructive()` call
instead of the now-bypassed `QMessageBox.question()`, for the same
reason the verification script needed the extra patch above.

### Risks

- None identified against business logic, the parser, extraction,
  search, or mapping — every change is either a dialog default button, a
  `setFocus()` call, or an additional keyboard-signal connection to an
  already-existing handler.
- The two workspace touches (Structure Builder, Page Alignment) are
  flagged explicitly above for the project owner's own review, since
  both are formally frozen; nothing there changes layout, wording, or
  business behaviour, only interaction plumbing.

### Recommended next sprint

- Per the project owner's roadmap: Sprint 15 — Error Reporting &
  Diagnostics, the next cross-cutting, application-wide sprint.

## Sprint 15 — Product Refinement: Error Reporting & Recovery

Date: 2026-08-05

Deliberately broadened by the project owner from "Error Reporting" to
"Error Reporting & Recovery": an operator rarely asks "why did it fail?"
— they ask "what do I do next?" This sprint's job was to standardize
recovery guidance, not just error wording, and to do it by centralizing
and reusing existing dialog infrastructure rather than rewriting it.

### Error/recovery audit (required "before making changes" deliverable)

**Every `show_error()` call site was inspected across the app.** The
`OutlineScreen` class (`main_window.py`, largely dead) is confirmed
**never instantiated and never added to `MainWindow.screens`** — several
`show_error`/`QMessageBox` calls inside it were explicitly excluded from
any fix, since no operator can ever see them.

**Two already-good patterns were found and treated as precedent to
generalize, not duplicate:**
- Page Alignment's `_format_approval_blocked()` (Reason / Action
  Required / Affected Section), added in Sprint 5 — already exactly the
  "Reason + recovery guidance" structure this sprint asks for
  everywhere. Left completely unchanged: Page Alignment is formally
  frozen (`docs/GOVERNANCE.md` §7) and already has its own passing test
  asserting the literal "Action Required" wording.
- `MainWindow.run_task()`'s "Task Failed" dialog (Sprint 13) — already
  built the exact `<b>Reason</b>.../<b>What you can do</b>...` structure
  inline, as a one-off. This became the template for the new shared
  helper, rather than being invented fresh.

**Four real gaps were found**: raw, unstructured `str(exc)` text with no
recovery guidance at all, in `StructureBuilder.import_csv()`,
`import_json()`, `import_json_text()`, and `approve()` (all in
`widgets/structure_builder.py`).

**Additional consistency gaps found**: `run_task()`'s own dialog and
`ExtractScreen.failed()`'s summary panel each built the same
Reason/What-you-can-do HTML inline via ad hoc f-strings (near-duplicate
code, not sharing a helper); `ExtractScreen.start()`'s pre-flight guard
and `LibraryScreen.add_pdfs()`'s two exception branches
(`LibraryImportError`, bare `Exception`) showed the underlying error with
no explicit recovery guidance.

**Already fine, left alone**: the 5 non-destructive `QMessageBox
.question()` calls (Sprint 14's own established restraint); status-bar
message durations (already a consistent 5000–7000ms range); `Severity
.BLOCKING`/`WARNING` validation presentation (already well-established
across Sprints 3, 5, 6, 9); several `QMessageBox.information()`/
`.warning()` calls in Structure Builder already reading as operator
language with implicit recovery guidance (e.g. "Include at least one
candidate before creating a draft.").

### Completed

- **New shared helper `format_operator_error(reason, next_steps)`** in
  `gui/widgets/dialogs.py` (alongside Sprint 14's
  `confirm_destructive()`), generalizing `run_task()`'s own Sprint-13
  dialog template: `<b>Reason</b><br>{reason}<br><br><b>What you can
  do</b><br>{next_steps}`. It only assembles what it's given — it never
  invents a placeholder reason or guidance, so the real diagnostic text
  is never silently discarded.
- **`run_task()`'s "Task Failed" dialog and `ExtractScreen.failed()`'s
  summary panel** both refactored to call the shared helper, removing
  the near-duplicate inline HTML construction.
- **Structure Builder's four raw-exception call sites** (`import_csv()`,
  `import_json()`, `import_json_text()`, `approve()`) now show plain
  operator language plus concrete next steps, with the original
  exception text and full traceback preserved in the existing expandable
  "Show Details" pane, never discarded. `approve()`'s single
  semicolon-joined `ValueError` from `OutlineService.approve()` is now
  split into one bullet per blocking issue, since each issue message was
  already operator language (e.g. "Section 3 has no title."), not
  exception jargon — it just needed to be shown as a list, not a
  run-on sentence.
- **`ExtractScreen.start()`'s pre-flight guard** now reuses the screen's
  own existing `IDLE_MESSAGE` constant as its recovery guidance, so the
  wording an operator sees on failure is identical to what they'd see on
  the idle readiness panel.
- **`LibraryScreen.add_pdfs()`'s two exception branches**
  (`LibraryImportError`, bare `Exception`) now both include "Check that
  the file is a valid, readable PDF and try adding it again," while the
  existing failure-stage/diagnostics/traceback details remain in the
  expandable pane, untouched.

### Already existed (verified, left unchanged)

- Page Alignment's Reason/Action Required/Affected Section format —
  confirmed still producing the identical 3-part structure via real GUI
  verification (see below), completely untouched.
- `Severity.BLOCKING` vs `Severity.WARNING` validation presentation
  across dry-run/readiness panels — reused as-is; this sprint added
  recovery guidance around *exceptions*, not a new validation
  presentation model.
- The 5 non-destructive `QMessageBox.question()` calls — unchanged,
  same restraint Sprint 14 already established.

### Behaviour intentionally left unchanged

- **No dialog redesign, no new exception hierarchy, no rewritten
  validation rules** — explicitly out of scope per the brief. Every
  fix reuses the existing `show_error(title, message, details)` contract
  and its already-present expandable "Show Details" pane.
- **Duplicate PDF registration continues to use `show_notice()`, not
  `show_error()`** — reconfirmed via real GUI verification. This is a
  recoverable, expected state (the book is already there), not a
  failure, so it deliberately stays a persistent notice rather than
  being pulled into the error-dialog structure this sprint standardized.
- **No new logging, telemetry, or crash reporting** — explicitly out of
  scope; every fix works within the existing `show_error()`/traceback
  plumbing.

### Existing functionality discovered

- `OutlineScreen` (main_window.py) is dead code — never instantiated,
  never reachable from `MainWindow.screens` — confirmed by grep and
  read, not assumed; its several unfixed `show_error()` calls are
  explicitly not a gap an operator can hit.
- `OutlineService.approve()`'s blocking-issue messages (e.g. "Section 3
  has no title.") were already written in plain operator language, not
  exception jargon — the fix only needed to split and bullet them, not
  rewrite their wording.

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`
(`BOOKCORPUSBUILDER_CONFIG` pointed at an isolated scratch project; the
real `data/` corpus was never touched), covering all 7 required
scenarios plus two retry-after-correction checks:

1. **Duplicate registration** (Library): re-adding the same PDF still
   produces a `show_notice()`, zero `show_error()` calls — confirmed
   unchanged.
2. **Library add failure** (simulated `shutil.copy2` disk-full):
   dialog now reads "Reason: `unreadable.pdf` could not be added to the
   library." / "What you can do: Check that the file is a valid,
   readable PDF and try adding it again," with the failure stage and
   full traceback still present in details.
3. **Validation failure / blocked approval** (Structure Builder, an
   entry with no title and no printed page): dialog now shows two real
   bullets — "Section 1 has no title." / "Section 1 needs a positive
   printed page." — plus "Correct the listed section(s) in the Review
   Outline table, then approve again," traceback preserved in details.
4. **Successful retry after correction** (same outline, title and
   printed page fixed): approval succeeds immediately after, zero
   errors, `ApprovalMetadata.approved` confirmed `True`.
5. **Mapping conflict** (Page Alignment, two disagreeing anchors on the
   same printed page): the dialog is confirmed **byte-for-byte the
   existing, unchanged** Reason/Action Required/Affected Section format
   from Sprint 5 — this sprint did not touch it.
6. **Successful mapping approval after correction** (disagreeing anchor
   removed, a second agreeing anchor added): approval succeeds, 2
   anchors persisted, zero errors.
7. **Extraction failure** (simulated `pdfplumber` read exception via a
   real `QThread`, pumped to completion): the real "Task Failed" dialog
   reads "Reason: simulated PDF read failure" / "What you can do: Review
   the reason above, then try again," traceback preserved; the screen's
   own summary panel independently shows the same Reason/What-you-can-do
   text plus "Nothing was written to your output folder," and the Cancel
   button is correctly disabled afterward.
8. **Configuration error** (`start()` invoked with no book selected,
   exercising the pre-flight guard directly rather than the background
   task): dialog reads "Reason: Select a book first." / "What you can
   do:" followed by the screen's own existing idle-state guidance
   verbatim — confirming the two messages are now identical, not just
   similar.
9. **Successful retry after correction** (same screen, valid PDF
   content supplied): extraction completes normally, zero errors,
   "✓ Extraction Complete" progress state, full completion summary
   shown.

One verification-script-only issue was found and fixed during this pass
(not an app bug): a first attempt manipulated `AlignmentScreen.mapping`
directly with hand-built `MappingAnchor` objects instead of going
through the screen's real `add_anchor()`/`remove_anchor()` methods,
which produced a mapping the app correctly rejected as still
unresolved — fixed by driving the same anchor form fields and buttons a
real operator would use. A second script-only issue — reading dialog
and summary-panel state immediately after a single `processEvents()`
call, before the real background `QThread` had actually finished — was
fixed by polling `processEvents()` until `MainWindow.threads` drains,
matching how a real event loop behaves rather than assuming a single
pump is enough.

### Test results

213/213 passing (204 pre-existing + 9 new: 2 in `tests/test_dialogs.py`
for `format_operator_error()` itself; 4 in
`tests/test_structure_builder.py` (`import_csv()`, `import_json()`,
`import_json_text()`, and `approve()`'s bulleted blocked-approval
reasons); 2 in `tests/test_library_screen.py` (`add_pdfs()`'s
`LibraryImportError` and bare-`Exception` branches); 1 in
`tests/test_extract_screen.py` (`start()`'s pre-flight guard). No
existing test needed rewriting — the new Reason/What-you-can-do text is
additive to messages every prior test already substring-checked.

### Risks

- None identified against business logic, the parser, extraction rules,
  search, mapping validation, or the exception hierarchy — every change
  is either a new shared string-formatting helper or a wording addition
  around an already-caught exception.
- `format_operator_error()` is now a second consumer, alongside
  `confirm_destructive()`, of `gui/widgets/dialogs.py` — a growing
  shared module worth keeping an eye on if it starts accumulating
  unrelated concerns.
- Structure Builder received further changes this sprint despite being
  formally frozen (`docs/GOVERNANCE.md` §7), for the same reason Sprint
  14 flagged: purely message-formatting/recovery-guidance changes, no
  layout, business logic, or exception-hierarchy change. Flagged
  explicitly here rather than silently done.

### Recommended next sprint

- Per the project owner's own framing, Sprint 15 was "the last major
  behavioural sprint before the project moves into documentation,
  polish, and release engineering." The natural next step is a
  **release-readiness / documentation pass**: an operator-facing manual
  or quick-start guide reflecting the now-stable interaction model
  (Sprints 7–15), plus a final pass confirming `docs/GOVERNANCE.md`'s
  workspace-freeze table and this log are both fully up to date before
  any tag or release is cut.

## Sprint 16 — Product Refinement: Product Consistency Audit

Date: 2026-08-05

Deliberately reframed by the project owner from "Documentation next" to
"Consistency next": documentation should describe a *finished* product,
and after fifteen sprints of independent, per-workspace improvements the
UI needed one pass to check it still reads as a single, coherent
application rather than the sum of its sprints. Explicitly **not** a
redesign — a wording/capitalization/icon harmonization pass across all
seven workspaces, with no new functionality and no business-logic
changes.

### Consistency audit (required "before making changes" deliverable)

Every live `QPushButton`, `QGroupBox` heading, table header row,
`show_error`/`show_notice` dialog title, `QMessageBox.question()` title,
status icon, tooltip, and empty/success-state message was inspected
across all seven workspaces (`main_window.py`, `widgets/structure_builder
.py`). `OutlineScreen` (main_window.py, confirmed dead code since Sprint
15 — never instantiated, never in `MainWindow.screens`) was excluded
entirely, same as last sprint.

**Button casing was split roughly evenly app-wide** between Title Case
("Save Draft", "Open Output Folder", "Best Fit Columns") and sentence
case ("Merge into current draft", "Choose output…", "Save local
settings") — not a case of one screen being wrong, but of the app never
having picked a single convention. Title Case was already the narrow
majority and matches Qt's own stock dialog buttons (OK/Cancel/Yes/No)
already used everywhere, so it was adopted as the one house style.

**Three buttons across three different workspaces did the exact same
thing** (`open_path()` on `self.book.path`, launching the source PDF in
the OS default viewer) under three different names: Library's "Open
PDF", Structure Builder's "Open PDF externally", Browser's "Open source
PDF". Confirmed by reading each handler, not assumed from the label.
Similarly, Run History's "Open selected output" and Extract's "Open Run
Folder" both call `open_path()` on a specific run's
`output_location` — same action, different words.

**Dialog titles mixed Title Case and sentence case** even among
`show_error()` calls added in the *same* sprint (Sprint 15's own
"Outline import failed" vs. "Could not add PDF").

**Table headers mixed conventions inside the same header row** —
Structure Builder's canonical outline table had "Review status"
(sentence case) sitting directly beside "Semantic Status" (Title Case,
added later); Library's table had "Last run" beside "Project Status" and
"Next Action". This was the clearest, most concrete evidence that the
inconsistency was real and not just a matter of taste.

**One diagnostic icon was a one-off**: Page Alignment's blocking-issue
list used "⛔" (no-entry sign) nowhere else in the app, while every other
blocking/failed state everywhere else (Library's summary marks, Extract's
"✗ Task Failed", Page Alignment's own two other `mark()` helpers two
lines above it) uses "✗". A single unexplained icon for the same
concept.

**Run History's empty state failed the brief's own test** ("why is this
empty → what do I do next?"): "No extraction runs recorded." states
why, but gives no next step at all — unlike Library's and Browser's
empty states, which both already do.

**A terminology mismatch was found within Structure Builder itself**:
its own editing-status line used "YES"/"NO" (all caps) for
modified/approved flags, while Library's table renders the identical
underlying boolean as "Yes"/"No" (Title Case) in its own Approved
column.

**Confirmed already consistent, deliberately left alone**: the
ALL-CAPS-banner-plus-Title-Case-fields convention used by both Extract's
readiness/completion panels and Settings' Configuration Summary (a
shared, intentional two-tier style: a big all-caps final verdict plus
Title-Case per-field detail) — this is a real, working cross-screen
convention, not an inconsistency, and was not touched. Tooltips: only one
static tooltip exists anywhere in the app (Best Fit Columns' button); no
duplicates or ambiguity to fix.

### Completed

- **Button labels standardized to Title Case** across Library, Structure
  Builder, Extract, Corpus Browser, Run History, and Settings (Page
  Alignment excluded — see below). Wording itself was only changed where
  two labels named the *same underlying action* differently: Library's
  "Open PDF" → "Open Source PDF" (now matching Structure Builder's and
  Browser's own renamed buttons), Library's "Reveal" → "Reveal Source
  PDF", Run History's "Open selected output" → "Open Run Folder"
  (matching Extract's identical action). Every other rename is
  capitalization-only — no action was renamed, merged, or invented.
- **Dialog titles standardized to Title Case**: Structure Builder's
  "Outline import failed" / "JSON outline import failed" / "Outline
  approval blocked" → Title Case; its "Create new outline" and "Revoke
  existing approval?" confirmation titles → Title Case (the latter also
  drops its "?", matching the other three confirmation dialogs in the
  app, none of which put the question mark in the title); Library's
  "Already in library" and Browser's "Cannot open run" notice titles →
  Title Case.
- **Table headers standardized to Title Case** in Structure Builder
  (both tables), Library, and Page Alignment (all three tables) — e.g.
  "Printed start" → "Printed Start", "Review status" → "Review Status",
  "Last run" → "Last Run", "PDF index" → "PDF Index".
- **Icon unified**: Page Alignment's blocking-diagnostic marker "⛔" →
  "✗", matching the one icon the rest of the app already uses for this
  concept.
- **Terminology unified**: Structure Builder's "YES"/"NO" → "Yes"/"No",
  matching Library's existing convention for the same underlying
  boolean.
- **Group box heading fixed**: Structure Builder's "Save and continue" →
  "Save and Continue", matching its own sibling headings ("Source",
  "Row Operations", "Structure") in the same tab.
- **Run History's empty state completed**: now reads "No extraction runs
  recorded." followed by "Next Step / Run an extraction from Workspace 4
  to see it listed here," matching Library's established why-then-what
  pattern.
- **Two stale cross-references caught and fixed during implementation**:
  Structure Builder's own empty-state guidance text quoted the old
  lowercase "Add from another source" button name; Browser's separate
  "Copy text" button (a different button from Structure Builder's, but
  the same underlying "copy visible text to clipboard" action) was
  brought in line with the same rename for full-app consistency.

### Already existed (verified, left unchanged)

- The Critical/Information icon split between `show_error()` and
  `show_notice()`, and the Question icon with a safe (No) default on
  `confirm_destructive()` — all centralized since Sprints 14–15, already
  fully consistent, not touched.
- `configure_table()`'s shared row height, selection colour, and
  frozen-column behaviour — every live table already goes through this
  one helper; this sprint changed header *text*, never the shared
  infrastructure itself.
- The ALL-CAPS-banner-plus-Title-Case-fields status convention shared by
  Extract and Settings — confirmed deliberate and consistent, not
  rewritten.
- Extract's dry-run "⊘" skipped-item marker — a genuinely distinct third
  state (skipped ≠ failed ≠ succeeded), not a duplicate of any other
  icon.

### Behaviour intentionally left unchanged

- **Page Alignment's button labels were not renamed**, despite mixing
  Title Case ("Suggest Next Anchor") and sentence case ("Add
  verification anchor", "Remove selected anchor", "Verify and approve
  mapping") within the same frozen workspace. Two things stopped this:
  the workspace is formally frozen (`docs/GOVERNANCE.md` §7), and unlike
  Structure Builder's equivalent buttons, these specific labels are
  cross-referenced by exact string in existing tests
  (`test_alignment_screen.py`) and in the panel's own status prose
  ("...then click Verify and approve mapping"). Renaming would have
  meant touching tested, frozen prose for a cosmetic gain — the
  Engineering Guidance's own instruction ("if an inconsistency cannot be
  resolved without changing behaviour/risk, document rather than
  change") applied directly. Only Page Alignment's table *headers* were
  changed (mechanical, no test dependency found, explicitly called out
  by requirement #4).
- **Page Alignment's own status/diagnostic prose** (`_format_approval
  _blocked()`, the suggestion panel's "Reason"/"Next action" wording) was
  left completely untouched, for the same reason Sprint 15 already
  protected it: frozen, tested, and not the specific gap this sprint was
  asked to close.
- **Extract's "READY FOR EXTRACTION" (header) vs. "SAFE TO EXTRACT"
  (footer status)** both describe the same ready/not-ready state in
  different words within the same panel — on inspection this looked
  like exactly the kind of duplication the brief's own example list
  warns about. Left unchanged: both strings are explicitly and
  separately asserted in existing tests as two deliberate messages (a
  technical headline plus a plain-language confirmation for a
  first-time operator), not an accidental duplicate.
- **No new logging, no new validation rules, no dialog redesign, no
  layout changes, no parser/extraction/mapping/search/settings-
  persistence changes** — explicitly out of scope, and none were made.

### Existing functionality discovered

- `open_path()` vs. `reveal_path()` (main_window.py) are genuinely
  different actions — `open_path()` launches a file directly,
  `reveal_path()` opens its *containing folder* (or the folder itself,
  for a directory) — confirmed by reading both helpers before assuming
  "Open" and "Reveal" buttons were interchangeable wording for the same
  thing anywhere in the app.
- Browser's "Reveal Output" and Extract's/History's "Open Run Folder"
  target different things (a specific exported file's parent vs. the
  run's own output folder as a whole) even though `reveal_path()` and
  `open_path()` behave identically when the target is already a
  directory — this is why Browser's button keeps "Reveal" while
  Extract's and History's keep "Open."

### Real GUI verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`
(`BOOKCORPUSBUILDER_CONFIG` pointed at an isolated scratch project),
walking all seven workspaces and asserting on live widget state, not
source text:
1. **Library** — every button label enumerated and confirmed Title Case;
   table headers confirmed ("Last Run" among them); a real duplicate-PDF
   add confirmed the notice dialog's real `windowTitle()` is now
   "Already in Library" (captured via a patched `QMessageBox.__init__`,
   not assumed); a real copy failure confirmed the error dialog title is
   "Could not add PDF."
2. **Structure Builder** — every button, both tables' headers, and every
   group-box heading enumerated from the live widgets; a real blocked
   approval (empty title, missing printed page) confirmed the dialog
   title is "Outline Approval Blocked"; a real approve-after-fix
   confirmed `editing_status.text()` now reads "Modified No · Approved
   Yes."
3. **Page Alignment** — all three tables' headers confirmed updated; all
   button labels confirmed genuinely unchanged (frozen); a real blocking
   condition (no anchors yet) rendered the diagnostics list and
   confirmed every blocking item now shows "✗", with zero "⛔" anywhere.
4. **Extract** — every button enumerated and confirmed Title Case.
5. **Corpus Browser** — every button enumerated, including the renamed
   "Open Source PDF," "Reveal Output," and "Copy Text."
6. **Run History** — buttons confirmed ("Open Run Folder," "Refresh Run
   History"); the empty-state label's live `.text()` and `.isVisible()`
   confirmed the new why-then-next-step wording actually renders when no
   runs exist.
7. **Settings** — every button enumerated and confirmed Title Case.

Run against an isolated scratch project; the real `data/` corpus was
never touched.

### Test results

213/213 passing — no new tests added (this was a wording/consistency
pass, not new behaviour to cover), but 5 pre-existing assertions were
updated to match the new, deliberately-changed strings: Structure
Builder's three dialog-title checks (Sprint 15's own tests) and its two
Yes/No editing-status checks.

### Risks

- None identified against business logic, the parser, extraction,
  mapping, search, or settings persistence — every change is a display
  string (button/heading/header/dialog-title text or a single status
  icon).
- Page Alignment and Structure Builder (both formally frozen) each
  received changes this sprint — Structure Builder's buttons/headings/
  dialog titles/terminology, Page Alignment's table headers only. Both
  are flagged explicitly here, consistent with Sprints 14–15's own
  precedent: purely cosmetic/wording changes, no layout or business
  logic touched.
- Two still-unresolved *documented* inconsistencies remain by deliberate
  choice (Page Alignment's button casing, Extract's two-tier ready
  wording) — flagged above rather than silently left, per the
  Engineering Guidance's own instruction to document rather than force a
  risky change.

### Recommended next sprint

- Per the project owner's own roadmap: **Sprint 17 — Documentation &
  Integrated Help.** The UI now has one consistent voice to document
  accurately (Title Case buttons/headings/tables/dialogs, one icon per
  concept, complete empty states) — an operator manual or quick-start
  guide written now will describe the actual, stabilized interaction
  model rather than needing a rewrite after the fact.

## Sprint 17 — Release Preparation: Documentation & Knowledge Transfer

Date: 2026-08-05

Deliberately reframed by the project owner from "Documentation" to
"Documentation & Knowledge Transfer," and from Product Refinement to a
new stage, **Release Preparation**: documentation should describe a
*finished* product, and after Sprint 16 the UI finally has one
consistent voice worth documenting accurately. This sprint made
**no application behaviour changes** — every change is to a `.md` file
or a regenerated screenshot.

### Documentation audit (required "before making changes" deliverable)

Every documentation artifact was compared against the live application,
not assumed current: `README.md`, `docs/OPERATOR_MANUAL.md`,
`docs/GUI.md`, `docs/GOVERNANCE.md`, `docs/ARCHITECTURE.md`, and all 20
operator-manual screenshots.

**`README.md`** claimed the GUI provides a "Library, **Outline**, Page
Alignment..." workspace list — "Outline" has never been a real
workspace name; the real one is "Structure Builder." A real, user-facing
factual error, not a wording nit.

**`docs/OPERATOR_MANUAL.md`** was stale in dozens of places — some from
Sprint 16 (last week: "Save local settings" → "Save Local Settings" and
similarly for ~15 other buttons/headers), but the Library workspace
screenshot proved the staleness went back much further: the *current*
Library screen has a right-hand "Book Summary" panel (added Sprint 9)
that the existing screenshot didn't show at all, and its button read
"Remove registration" — a name that predates even the current "Hide
from Library" wording. The manual's own status line claimed "Manual
status: Current — reflects the application exactly as installed,"
which was not true at the time this sprint began.

**`docs/GUI.md`** hadn't been updated since "v0.2.1" (Sprint ~9–12 era)
and had no mention at all of Sprints 13–16's shared task lifecycle,
keyboard/navigation work, error-recovery structure, or consistency
pass — a real developer-facing document silently missing four sprints
of now-load-bearing behavior.

**`docs/ARCHITECTURE.md`**'s file tree omitted five real, current
modules (`outline_contract.py`, `outline_contract_repository.py`,
`outline_hashing.py`, `outline_validation.py`,
`ollama_outline_generator.py`) and three top-level directories
(`schemas/`, `scripts/`, `tests/`).

**`docs/GOVERNANCE.md`** was largely accurate (the 7-workspace list
there already correctly said "Structure Builder," unlike README) but
its Lifecycle section (§6) didn't cross-reference the "Workspace
Maturation / Product Refinement / Release Preparation" sub-stages
already implicit in `UX_SPRINT_LOG.md`'s own sprint titles.

**A first-run guidance contradiction was found**: `README.md` tells a
new maintainer to build a fresh `.venv`, while
`docs/OPERATOR_MANUAL.md` Chapter 3 warns that the project's own
`.venv` is a "known-broken build environment" and to use a sibling
`../BOOKCORPUSBUILDER-gui-venv` instead, per an open item in
`docs/IMPROVEMENT_ROADMAP.md` Phase 1. Both are true simultaneously (a
fresh checkout vs. this specific retained checkout) but the manual
never explained the distinction, reading as a flat contradiction.

**A real, previously-undiscovered layout defect was found** while
capturing real screenshots for this sprint: Settings' "Configuration
Summary" panel and Page Alignment's "Verification Status"/"Verification
Workflow" panels can visually overlap adjacent content when the
application window is short enough that their dynamic, multi-line
status text doesn't fit the space initially reserved for it — confirmed
reproducible at a 1600×900 window and not reproducible at 1600×1300.
Per this sprint's own Engineering Guidance ("if documentation reveals a
product inconsistency, document it and defer any code change"), this
was **not fixed** — it is recorded in `Release_Notes_v1.0_DRAFT.md`'s
"Known limitations" for Sprint 18 to investigate under real (non-
offscreen) display conditions.

### Completed

- **`README.md`**: fixed the "Outline" workspace-name error; added a
  "Maintainer and release documentation" section linking the four new
  documents below.
- **`docs/OPERATOR_MANUAL.md`**: every stale button label, table header,
  and dialog title updated to match the live Sprint 14–16 application
  (roughly 20 distinct corrections across Chapters 5–15); added the
  missing "Semantic Status" column to Chapter 9's table description;
  generalized Chapter 18's closing paragraph, which previously implied
  the Reason/What-you-can-do error structure was Page-Alignment-
  specific, when Sprint 15 made it universal; added a short note to
  Chapter 14 documenting that the first search result is now shown
  automatically, discovered while re-capturing Figure 18; added the
  Chapter 3 venv-contradiction clarification and a Chapter 15 note
  describing Run History's empty state.
- **`docs/GUI.md`**: fixed the two remaining stale button names; added a
  new section summarizing Sprints 13–16's shared task lifecycle,
  navigation, error-recovery, and consistency work.
- **`docs/ARCHITECTURE.md`**: file tree corrected to include the five
  missing modules and three missing top-level directories.
- **`docs/GOVERNANCE.md`**: Lifecycle section (§6) now cross-references
  the existing Workspace Maturation / Product Refinement / Release
  Preparation sub-stages already used in `UX_SPRINT_LOG.md`'s own sprint
  titles — synchronizing an existing, already-used concept, not
  introducing a new governance rule.
- **`docs/UX_SPRINT_LOG.md`**: Sprint 16's own header was missing the
  "Product Refinement:" prefix every other Stage-2 sprint uses;
  corrected for consistency.
- **19 of 20 operator-manual screenshots regenerated** from the real,
  live application (offscreen Qt, an isolated scratch
  `BOOKCORPUSBUILDER_CONFIG` project, the same three fixture PDFs the
  manual already references) — not redrawn or mocked. Figure 21
  (the output-folder tree) was deliberately left untouched: the on-disk
  folder layout it depicts has not changed in any sprint.
- **Four new documents**: `docs/UX_SPRINT_SUMMARY.md` (one line per
  sprint, for maintainers), `docs/Release_Notes_v1.0_DRAFT.md` (draft
  only — no release announced), `docs/DEVELOPER_HANDOVER.md`
  (architecture orientation, frozen-workspace rules, extension points,
  coding philosophy), and this sprint's own log entry.

### Behaviour intentionally unchanged

- **No application code was modified.** Every change in this sprint is
  to a `.md` file or a `.png` screenshot; the regression suite was
  re-run after every batch of edits specifically to catch any accidental
  code change, and it never moved from 213 passing.
- **The layout-overflow issue found in Settings/Page Alignment was not
  fixed** — deferred to Sprint 18 per this sprint's own charter (see
  above).
- **The `.venv`-vs-`../BOOKCORPUSBUILDER-gui-venv` question was not
  resolved** (i.e., no `.venv` was rebuilt, no roadmap item checked off)
  — only clarified in the manual so the two existing, both-true
  instructions stop reading as a contradiction. Recreating `.venv` is
  `docs/IMPROVEMENT_ROADMAP.md` Phase 1, H1 — out of scope here.
- **`docs/PROJECT_AUDIT_REPORT.md`, `docs/REORGANIZATION_AUDIT_2026-08-
  03.md`, and `AUDIT_PACKAGE.md` were deliberately left untouched.** All
  three are explicitly dated, point-in-time historical snapshots (the
  first two say so in their own header); rewriting them to reflect
  current reality would destroy their value as a historical record, not
  improve documentation.
- **Page Alignment's and Structure Builder's frozen wording/prose were
  not touched** in this sprint at all — Sprint 16 already made that
  determination for the button/dialog text itself; this sprint only
  updated the *manual's description* of them to match what Sprint 16
  actually shipped.

### Existing functionality discovered

- The real Library workspace has had a "Book Summary" side panel since
  Sprint 9 — entirely undocumented and unshown in any prior screenshot.
- Corpus Browser's search already auto-selects and previews the first
  result as soon as a search completes — the manual previously implied
  this required a separate, subsequent click.
- `docs/IMPROVEMENT_ROADMAP.md` Phase 1 already contains the open,
  unchecked item explaining exactly why two different Python
  environments are referenced across this project's documentation —
  the contradiction was documented years before this sprint's audit
  independently rediscovered it from the operator side.

### Verification performed

Real GUI, offscreen Qt platform, against the actual `MainWindow`
(`BOOKCORPUSBUILDER_CONFIG` pointed at an isolated scratch project; the
real `data/` corpus and library were never touched). Every documented
workflow chapter was exercised for real, in the order the manual
presents it, using the manual's own three fixture PDFs
(`fixture_a_normal.pdf`, `fixture_b_frontmatter_offset.pdf`,
`fixture_c_scanned.pdf`): register three books; select and inspect one;
paste-parse-review-approve an outline (`fixture_a`, the manual's own
"Foundations/Structures/Continuity" example text); build, verify, and
approve a three-anchor page mapping reproducing the manual's own worked
example exactly (`fixture_b`, printed pages 1/10/21 → physical 4/13/24);
run a real dry run and a real extraction; search the real extracted
text for "sovereignty" (present in `fixture_b`'s real body text) and
confirm the result preview and source-PDF jump; and confirm Run
History lists the completed run. Every button, table header, and
dialog title asserted against in this pass was read from live widgets,
not from the markdown being corrected. One capture-time bug was found
and fixed in the verification script itself (not the app): grabbing a
screenshot from inside a cross-thread progress-signal handler segfaulted
PySide6's offscreen platform; fixed by driving `on_progress()`
synchronously for the illustrative "in-progress" frame instead, then
running the real threaded extraction separately for the "complete" one.

### Test results

213/213 passing, unchanged from Sprint 16 — expected and required for a
documentation-only sprint; re-run after every batch of edits.

### Risks

- None against business logic, the parser, extraction, mapping, search,
  or settings persistence — nothing in `src/` was touched (verified by
  file-modification-time check in addition to the regression suite).
- The Settings/Page Alignment layout-overflow finding is a real,
  reproducible UI issue, not fixed here by design — flagged in three
  places (`Release_Notes_v1.0_DRAFT.md`, this entry, and left as a
  Sprint 18 recommendation) so it cannot be lost before the next sprint
  picks it up.
- Four of the twenty screenshots (10–13, Page Alignment) still show two
  minor, cosmetic residual overlaps in their busiest state even at the
  taller capture window — legible and materially accurate, but not
  pixel-perfect. Noted rather than hidden.

### Recommended next sprint

- Per the project owner's own roadmap: **Sprint 18 — Release Hardening
  & Release Candidate.** `Release_Notes_v1.0_DRAFT.md`'s own closing
  section lists exactly what that sprint needs to do: final regression
  audit (including the layout-overflow finding under real display
  conditions if available), governance audit, dead-code review
  (`OutlineScreen` has been confirmed unreachable since Sprint 15),
  packaging verification and a versioning decision, a release
  checklist, and the v1.0 release candidate itself.

## Sprint 18 — Release Candidate Audit

Date: 2026-08-05

Deliberately reframed by the project owner from a development sprint to
an **independent release audit**: "Build the software" becomes "Prove
the software is ready." This sprint made **no product improvements by
design** — its mission was to evaluate the existing product honestly,
not to change it, and to fix only true release blockers if any were
found. None were.

### Audit findings (all phases)

**Phase 1 (code audit).** Confirmed `OutlineScreen` (`main_window.py:
368–777`, 410 lines) is unreachable — `MainWindow.__init__`'s
`self.screens` list skips directly from `LibraryScreen` to
`AlignmentScreen`. New this sprint: `gui/services/assistance.py`'s
`TocIndexService` (76 lines) is called *exclusively* from within
`OutlineScreen` and has zero other callers and zero test coverage,
making it transitively dead as well — a finding Sprint 15/17 hadn't
extended to the service layer. A systematic usage-count audit across
every class definition in `src/` found no other dead widgets or
screens. No TODO/FIXME/XXX markers exist anywhere in `src/`. Three
orphaned screenshot files and one undocumented scratch file
(`bookcorpusbuilder.txt`) were found at repository level.

**Phase 2 (regression verification).** 213/213 passing across 3
consecutive runs (no flakiness), 0 skipped, 0 warnings, and —
independently re-verified rather than assumed — 213/213 passing from a
completely fresh `pip install -e '.[gui,dev]'`, not just the retained
development environment.

**Phase 3 (workspace audit).** A 26-check real-GUI walkthrough (startup,
all 7 workspaces' navigation, 4 workspaces' empty states, a full real
pipeline run register→structure→align→extract→search→history on
`fixture_b_frontmatter_offset.pdf`, a blocked-state recovery, and clean
shutdown with settings persistence) passed 26/26 with zero exceptions.

**Phase 4 (documentation audit).** Re-verified Sprint 17's corrections
held, and found one new staleness this same sprint's earlier work had
already introduced: `UX_SPRINT_SUMMARY.md` described Sprint 17 as "in
progress" after it had completed. Fixed on discovery. Found and
recorded (not fixed): `docs/IMPROVEMENT_ROADMAP.md`'s Phase 0 doesn't
state that its page-offset corruption findings describe the legacy CLI,
not the GUI — a real scope-clarity gap a reader could misinterpret as
an open v1.0 GUI blocker.

**Phase 5 (governance audit).** Found a real traceability defect: a
Sprint 17 edit to `GOVERNANCE.md` §6 had never been logged in the
amendment log or the header's `Amended:` line, as the document's own §8
self-amendment protocol requires. Fixed on discovery (see "Behaviour
intentionally unchanged" below for why this, uniquely, was corrected
rather than merely logged).

**Phase 6 (packaging audit).** The single most consequential finding of
this sprint: **the repository has no version control** — no `.git`
directory exists despite an actively-maintained `.gitignore`. Also
found: no `LICENSE` file and no `license` field in `pyproject.toml`; the
project's retained `.venv/` genuinely has a broken interpreter binary
("cannot execute binary file: Exec format error"), confirming (not just
trusting) the Operator Manual's existing warning — but a **completely
fresh** `venv` built exactly per `README.md`'s own instructions
installs cleanly, passes the full suite, and successfully builds a real
distributable wheel, proving the *package* itself is sound even though
the *retained development environment* is not.

### Completed

- `KNOWN_ISSUES.md`, `RELEASE_CHECKLIST.md` (38 items, each with cited
  evidence), and `RELEASE_CANDIDATE_REPORT.md` (final verdict: **GO
  WITH KNOWN ISSUES**), all at the repository root.
- `docs/UX_SPRINT_SUMMARY.md` and `docs/Release_Notes_v1.0_DRAFT.md`
  updated to close the loop with this sprint's own findings, and to
  stop describing Sprint 17/18 as still in progress.
- `docs/GOVERNANCE.md` — the missing Section 6 amendment logged (see
  Phase 5 above); no other governance content changed.

### Behaviour intentionally unchanged

- **No application code was modified.** This was the sprint's explicit
  charter, and it held: zero release blockers were found in the
  audited product, so nothing needed fixing under the "only fix true
  release blockers" instruction.
- **`OutlineScreen` and `assistance.py` were not deleted**, despite
  being conclusively confirmed dead — "produce findings first," per
  this sprint's own Phase 1 instruction; recorded in `KNOWN_ISSUES.md`
  as Cosmetic, left for a future sprint to action.
- **Git was not initialized**, despite being this audit's most
  significant finding. Deciding what belongs in version control (real
  copyrighted source PDFs currently sit in `data/input/pdfs/`; whether
  to synthesize any history; whether to keep the broken retained
  `.venv/`) is a project-owner decision this audit is not positioned to
  make unilaterally, and `docs/IMPROVEMENT_ROADMAP.md` already records
  it as a deliberately open item, not an oversight.
- **No LICENSE was chosen or added** — a decision, not a mechanical
  fix.
- **The Section 6 governance amendment was the one exception to
  "document, don't fix."** It was corrected on discovery rather than
  only logged in `KNOWN_ISSUES.md`, because it was a traceability defect
  in an already-authorized Sprint 17 change (making it consistent with
  its own document's rules), not a new scope or product decision
  requiring fresh authorization — the same distinction Sprint 17 itself
  drew when it made the original edit.

### Existing issues discovered

See `KNOWN_ISSUES.md` in full. Highlights not previously known to any
prior sprint: the transitively-dead `assistance.py`; the confirmed-
broken retained `.venv/` interpreter (previously only described
secondhand, via the Operator Manual and roadmap, never independently
verified); the missing LICENSE; and the absence of version control.

### Verification performed

Real GUI, offscreen Qt platform, exactly as prior sprints — plus, new
for this sprint, two additional forms of independent verification a
pure code/documentation audit would not have caught: (1) a completely
fresh, isolated `python3 -m venv` + `pip install -e '.[gui,dev]'`,
re-running the full test suite and smoke-testing every CLI entry point
and the GUI entry point from that fresh install, not the retained
development environment; and (2) a real `python -m build --wheel`,
confirming a distributable artifact actually builds and contains the
expected files. Build artifacts (`build/`, `*.egg-info/`, the temporary
fresh venv) were cleaned up after verification and are not part of the
repository.

### Test results

213/213 passing, stable across 3 consecutive runs, reproducible from a
completely independent fresh install. Unchanged from Sprint 17 — no
code was modified this sprint either.

### Remaining risks

See `RELEASE_CANDIDATE_REPORT.md`, "Risks," in full. The two load-
bearing ones: no version control (this project cannot currently be
checked out by a tag, diffed, or rolled back), and no declared license
(a real gap for any use or distribution beyond the current private
context). Both are release-process gaps, not defects in the audited
application, and neither was introduced by this sprint — both were
found, not created.

### Recommended next sprint

- This sprint's own `RELEASE_CANDIDATE_REPORT.md` recommends
  **v1.0.0-rc1**, not an unqualified `v1.0.0`, specifically because of
  the two release-process gaps above. The natural next step is not
  another sprint in this programme, but a project-owner decision on
  version control and licensing — after which a short confirmation
  pass (not a full re-audit) against just those two items should be
  sufficient to justify the unqualified `v1.0.0` tag this eighteen-
  sprint programme has otherwise already earned.

---

## Post-release architecture change — Page Alignment merged into Structure Builder

Date: 2026-08-05

Not a numbered UX sprint (Phase 3/Maintenance is active, per
`docs/GOVERNANCE.md` Section 6 — the sprint programme is closed). Recorded
here because Section 7 names this file as the authoritative record of
workspace freeze/merge status, and both workspaces involved were frozen.

**What changed:** Workspace 3 (Page Alignment) no longer exists as a
standalone workspace. Its verification UI (`AlignmentScreen`) was moved into
Workspace 2 (Structure Builder) as a third tab, "C. Page Mapping", alongside
the existing "A. Create Structure" and "B. Review Outline". The application
is now six workspaces: Library, Structure Builder, Extraction, Corpus
Browser, Run History, Settings.

**Why:** project owner's direction — every outline node already carries its
own `printed_start` / `physical_start` / `pdf_page_index`, so reviewing
structure and reviewing page mapping were two workspaces looking at the same
underlying entries from two angles. Merging them into one review pass
removes duplicate navigation and keeps an outline entry and its page
location reviewed together instead of separately.

**What did not change:** `PageMapping`, `MappingAnchor`, `MappingService`
(anchors, segments, conflict/diagnostic detection, approval gating), and the
extraction pipeline's dependency on an approved mapping are all untouched —
same classes, same persistence, same algorithm. This was a UI relocation,
not a data-model or pipeline change. `AlignmentScreen` was renamed
`PageMappingPanel` and now lives in `widgets/page_mapping.py`; it takes
Structure Builder's existing shared `PdfTextPreview` instance instead of
owning a second, independent preview pane (previously each workspace had
its own preview, which could show different pages of the same book at
once).

**Verified:** full test suite (213 tests, migrated `test_alignment_screen.py`
→ `test_page_mapping.py`) passing; real-GUI rendering checked at 1920×1080
and 1366×768 (offscreen Qt platform) across all three Structure Builder
tabs, confirming no row overlap or clipping on the new Page Mapping tab —
the tab required its own vertical scroll area once nested inside Structure
Builder's own splitter/tab chrome, since the anchors/segments/mapping-preview
tables plus their action rows no longer fit unscrolled at 1366×768.

**Freeze status after this change:** Structure Builder (WS2) remains frozen
per Section 7 — this merge was the explicit "(b) new approved roadmap"
exception, not a reopening for routine enhancement. Further changes to
Structure Builder (including its new "C. Page Mapping" tab) again require a
demonstrated regression or another explicit new roadmap decision.

---

## Post-release defect fixes — Structure/mapping taxonomy, JSON import, and page-resolution priority

Date: 2026-08-05 (same day, continuation)

Also not a numbered UX sprint (Phase 3/Maintenance active). A sequence of
real defects surfaced and fixed via a live operator's actual book data,
each verified against the running application before being called fixed —
recorded here per the same Section 7 authoritative-record convention as the
merge entry above.

### 1. Four unsynced "allowed kind" lists

`EntryKind` (the `book_outline_contract` enum), `services/outlines.KINDS`,
`json_outline_importer.ACCEPTED_KINDS` (a fifth list, found during this
pass), Structure Builder Tab A's dropdown, and the operator-supplied
`docs/BOOK_STRUCTURE_PROTOTYPE_KEY.json` each declared a different set of
valid section kinds. Reconciled to one 16-value union (`part, chapter,
section, subsection, analytical_section, preface, introduction, appendix,
bibliography, notes, index, caption, topic, glossary, acknowledgement,
other`) additive to the frozen contract, backward-compatible. Tab A's
dropdown now derives from `KINDS` (`tuple(sorted(KINDS))`) instead of its
own hardcoded copy, closing off future drift at that call site.
Regenerated `schemas/book_outline_contract_v1.schema.json`, a checked-in
snapshot a test asserts matches the live Pydantic schema exactly.

### 2. `physical_start`/`pdf_index` silently dropped on JSON import

`OutlineCandidate` — what every imported row becomes — had no
`physical_start`/`pdf_page_index` fields at all, in *both* JSON import code
paths (the flat/list format and the `book_outline_contract` schema format).
Added the fields, threaded them through `to_outline_entry()`, added the two
columns to Tab A's candidate preview table with the same
`pdf_index == physical_start - 1` validation used elsewhere, and added
regression tests.

### 3. The mapping engine ignored supplied `physical_start`/`pdf_index` entirely

The more consequential defect: `PageMapping.resolve()` only ever consulted
anchors/segments, never an entry's own supplied coordinates — so an
outline imported with a fully-specified page mapping for every row still
required the operator to manually re-derive it via anchors, and every
un-anchored row was reported as a diagnostics warning. Added
`PageMapping.resolve_entry(entry)`, preferring a self-consistent supplied
`physical_start`/`pdf_page_index` pair (a new `"supplied"` resolution
method) over anchor inference, propagated to every call site with entry
access — critically including `services/extraction.py` and
`services/validation.py`, where the same gap meant **actual extraction**,
not just UI warnings, would silently fail for any section whose only page
evidence was JSON-supplied. Also relaxed `MappingService.validate()`'s
blanket "need ≥2 anchors" gate to only fire when some entry genuinely isn't
already resolved.

### 4. `OutlineService.validate()` forced Roman-only entries into a fake numeric page

Front matter with only a Roman page label (e.g. a Preface at "ix", with no
Arabic `printed_start`) could not be approved even with a fully resolved
`physical_start`/`pdf_page_index`, because approval unconditionally required
a positive numeric `printed_start`. This is what pushed an operator to
enter a fabricated `printed_start: 1` for a Preface just to get past
validation. Fixed: a Roman `printed_page_label`, or a self-consistent
supplied physical/pdf-index pair, now each independently satisfy this
check without a numeric printed page.

### 5. Known, not fixed: stale `page_count`

Diagnosed but deliberately left open — see `KNOWN_ISSUES.md` MED-5.
`LibraryService.books(inspect=False)` (the routine refresh path) never
re-scans an already-registered book's PDF, so a stale `page_count` can
under-count a book indefinitely with only "Refresh" as the manual fix.

**Verified:** 219/219 tests passing (regression tests added for the
zero-anchor validate/approve path, zero-anchor real extraction via
`ExtractionService`, and JSON-import coordinate validation), plus real-GUI
screenshots of an operator's actual book data (Preface/Introduction/8
chapters/notes/index, 96 rows) confirming `READY FOR APPROVAL` with zero
blocking issues and every resolvable row showing `method: supplied`.

**Freeze status:** Structure Builder (WS2), including its "C. Page Mapping"
tab, remains frozen per Section 7. Items 2–4 above are demonstrated
regressions/defects (Section 7 exception (a)), not routine enhancements —
each was confirmed against real, reproducible failures (a real import
silently losing fields, real extraction failing, a real approval being
blocked) before being fixed.
