# Desktop GUI

The PySide6 application exposes the Generation 3 workflow without invoking the
CLI through subprocesses:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[gui,dev]'
.venv/bin/bookcorpus-gui
```

The retained historical `.venv/` in this working copy may not be executable on
another machine. Recreate it locally when necessary; `.idea/` remains available
for PyCharm project settings.

For isolated testing or alternate machine-local profiles, set
`BOOKCORPUSBUILDER_CONFIG` to a settings JSON file before launch. This redirects
library registration, outlines, outputs, run history, and logs without changing
the canonical defaults.

## Workspaces

1. **Library** — hash-based PDF registration, duplicate detection, native-text
   status, search, system open/reveal, and non-destructive deregistration.
2. **Structure Builder** — persistent PDF text reference beside separate
   Create Structure and Review Outline modes, deterministic candidate parsing,
   conservative merge preview, canonical review, and approval metadata.
3. **Page Alignment** — two-anchor offset verification, exceptional mappings,
   and printed/physical/index mapping preview.
4. **Extract** — blocking preflight, dry run, worker-thread execution,
   cancellation, progress counts, and structured logs.
5. **Corpus Browser** — title/full-text search, contextual snippets, filters,
   metadata, TXT/JSONL/manifest access, copy, export, and reveal operations.
6. **Run History** — immutable run records and output access.
7. **Settings** — ignored machine-local paths and scan/extraction defaults.

## Resizable tables and panes (v0.2.1)

Every table header is interactive and movable. Visible separators provide a
clear drag target in dark themes; divider double-click fits one column, the
header context menu controls optional column visibility and layout reset, and
**Best Fit Columns** fits the current contents. Shift-wheel scrolls
horizontally. Identifier columns are frozen while later metadata columns
scroll.

Header state—widths, order and visibility—is persisted per table in the active
settings profile. Main splitters, the Corpus Browser result/detail divider and
window geometry are persisted the same way. Defaults give title/section fields
approximately 500 pixels, while high-resolution monitors receive a larger
initial window. No table uses a global stretch mode that removes operator
control of the dividers.

## Paste an outline

Select a book in Library and open Structure Builder. Create Structure presents
six explicit sources: paste an outline, detect from the PDF, import CSV,
import structured JSON, generate with optional local Ollama, or build manually. Existing drafts load in Review Outline. Copy a table of
contents from the built-in text preview, the system PDF viewer, or any other
source, paste it, and choose **Parse Preview**.

The deterministic parser recognises dotted leaders, ordinary trailing page
numbers, chapter/part labels, hierarchical numbering, comma/pipe/tab-delimited
rows, wrapped titles, and Roman front-matter labels. Ambiguous and repeated
header lines remain visible with warnings instead of being silently discarded.
The candidate table allows inclusion, serial number, title, kind, printed page,
and hierarchy level to be corrected without changing the current draft.
Pipe-delimited hierarchical identifiers such as `1.1 | Section title | 7`
are stored as source serial provenance, used to establish hierarchy, and never
left inside the candidate title; canonical integer serial numbers remain
unique.

**Import JSON…** accepts either a flat array of outline objects or a document
object containing `book` metadata and an `outline` array. Nested `children` are
flattened for preview while `sno`/`parent_sno` hierarchy, row source, and the
SHA-256 hash of the raw import are retained. JSON is validated independently of
the free-form parser. Unknown keys appear in a non-blocking diagnostics panel
and never become candidates. A row whose `printed_start` is `null` remains
visible as analytical metadata with `missing_printed_page`, but is unchecked
until an operator supplies a page. JSON pasted into the normal editor prompts
for structured import and is never silently parsed or accepted.

The preferred JSON form is `book_outline_contract` v1.0.0, defined by strict
Pydantic models and the generated
`schemas/book_outline_contract_v1.schema.json`. Contract import verifies
document identity, parent references, levels, coordinates, lifecycle metadata
and analytical-boundary safety. Imported contract candidates are stored under
the book's versioned contract folder only after the operator explicitly creates
a draft.

**Generate with Ollama…** is an optional local candidate source. It submits the
same generated schema, requires an unvalidated draft response, and then follows
the ordinary candidate preview. It cannot approve an outline or invoke
extraction. Proposed analytical entries stay unchecked and validation blocks
them as boundaries until verified.

After review, **Create New Outline** replaces only an unapproved draft after
confirmation. An approved clean outline remains protected; a revised draft is
stored separately. **Merge into Current Draft** first reports new, matching,
conflicting, and ignored rows. Conflicts default to keeping the draft and can
individually use the candidate, keep both, or remain excluded. Original source
text, parser rules, confidence, warnings, and user-edit status are retained in
an `*_outline_sources.json` provenance sidecar rather than bloating the CSV.

Review Outline remains the authoritative table. It separates printed labels,
physical pages, and zero-based PDF indices; groups blocking errors, warnings,
and passed checks; and provides local clipboard exports. Save and approve there,
then continue to Page Alignment. Editing an approved canonical row revokes its
approval, while accepting candidates never bypasses validation or mapping.

## Safety contract

GUI extraction never assumes a zero page offset. It requires all of the
following before work begins:

- an unchanged source PDF;
- an approved clean outline whose hash still matches its approval sidecar;
- a page mapping verified by at least two agreeing non-exception anchors;
- valid, monotonic, in-bounds physical pages;
- unique section numbers and output filenames.

Extraction builds inside a run-scoped temporary directory. Cancellation or
failure removes that temporary output. A successful run is atomically promoted
to `data/output/runs/<run_id>/`, and its record is retained under
`data/output/run_history/`.

## Shared task lifecycle, navigation, error recovery, and consistency (v0.2.1, Sprints 13–16)

Every background operation (detection, extraction, Ollama generation) runs
through one shared `run_task()` path: a header task indicator shows what is
running, a "Last action: … succeeded/failed" label always reflects the most
recent attempt, and a failed task both resets the calling workspace's own
in-progress UI state and shows a standard error dialog — no background task
can silently fail with the workspace left stuck mid-run.

Every operator-facing error dialog (`show_error()`) uses one shared structure:
a plain-language "Reason," a concrete "What you can do" next step, and the
full technical exception/traceback preserved behind an expandable "Show
Details" section — never a bare exception message, and never a discarded
traceback. Destructive confirmations (deleting a row, clearing pasted text)
default their dialog to "No," not "Yes," unlike the plain informational
Yes/No dialogs used elsewhere. Enter/Return in Page Alignment's anchor fields
adds the anchor directly, and focus returns to the relevant table after a
mouse-driven Add/Delete/Move/Remove action rather than being left stranded on
the button just clicked.

Button labels, dialog titles, table headers, and status icons use one
consistent style across all seven workspaces (Title Case for controls and
headers, a single "✗" for any blocked/failed state, one wording per action —
e.g., "Open Source PDF" appears identically in Library, Structure Builder, and
Corpus Browser rather than three different phrasings for the same action).
Page Alignment is the one exception: its own button wording and status prose
were deliberately left as they were when the workspace was frozen, rather than
renamed for cosmetic consistency alone.

## Current limitations

- The preview is native extracted text rather than a rendered PDF canvas.
- Opening a source reference delegates to the system PDF viewer; exact-page
  navigation depends on that viewer.
- OCR availability is detected, but OCR execution is not implemented.
- The legacy `bookcorpus-extract` CLI has not yet been migrated to the GUI's
  verified page-mapping service.
- Focused widget tests run with Qt's offscreen platform in the retained GUI
  environment; rendered-page PDF acceptance still requires a display-capable
  environment because this cycle intentionally retains the native-text preview.
