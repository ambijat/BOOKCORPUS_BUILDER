# BOOKCORPUSBUILDER

BOOKCORPUSBUILDER turns book-length PDFs into a human-reviewable outline and
then into section-level text, JSONL, and manifest outputs. The repository was
reorganized in August 2026 so code, inputs, intermediate work, generated data,
experiments, and historical material no longer overlap.

## Setup

Python 3.10 or newer is required. Existing `.venv/` and `.idea/` directories
remain at the project root for PyCharm and local-tool compatibility. The
current copied environment may not execute on every machine; recreate it only
when appropriate for your local setup.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Install optional analysis, TTS, and development dependencies with:

```bash
.venv/bin/pip install -e '.[analysis,tts,dev]'
```

For the desktop application, install the GUI dependency and launch it with:

```bash
.venv/bin/pip install -e '.[gui]'
.venv/bin/bookcorpus-gui
```

The GUI provides Library, Structure Builder, Page Alignment, Extract, Corpus
Browser, Run History, and Settings workspaces. Extraction remains disabled until a
clean outline is approved and a printed-to-physical page mapping has been
verified against at least two anchors.

The Structure Builder is paste-first: copy a table of contents from the PDF or
another source, parse it into a candidate preview, correct hierarchy and page
labels, then explicitly create or conservatively merge a draft. Interactive
tables provide frozen identifiers, persistent column layouts, best-fit
controls, header visibility menus, horizontal wheel scrolling and saved
splitter panes. The separate
Review Outline mode remains authoritative for saving and approval before page
alignment. Native flat/nested JSON import has its own validator and diagnostics;
PDF detection, CSV import, and manual construction feed the same
candidate model and provenance trail.
Hierarchical pipe rows such as `1.1 | Section title | 7` preserve `1.1` as
source provenance while producing a clean title and a unique canonical serial.

`book_outline_contract` v1.0.0 is the strict Python/JSON interchange contract.
Its generated schema is in `schemas/book_outline_contract_v1.schema.json`.
Verbatim printed structure and proposed analytical structure have distinct
boundary permissions; unverified analytical entries cannot become extraction
boundaries. Optional local Ollama support (`.[ollama]`) can generate only
schema-constrained, unvalidated draft candidates for normal human review.

## Operator documentation

- [Complete Operator Manual](docs/OPERATOR_MANUAL.md) — searchable repository source.
- [Complete Operator Manual (DOCX)](docs/BOOKCORPUSBUILDER_Operator_Manual_v0.2.1.docx) — formatted copy for printing and distribution.
- [Desktop GUI notes](docs/GUI.md) — concise implementation and safety reference.
- [Product brochure](docs/BOOKCORPUSBUILDER_Brochure.md) — concise capabilities and governance overview.
- [Product brochure (DOCX)](docs/BOOKCORPUSBUILDER_Brochure.docx) — formatted brochure for distribution.

## Maintainer and release documentation

- [Developer Handover](docs/DEVELOPER_HANDOVER.md) — architecture orientation, frozen workspaces, extension points, and coding philosophy for a new contributor.
- [Governance](docs/GOVERNANCE.md) — the normative rules every change must pass, and the workspace-freeze table.
- [UX Sprint Summary](docs/UX_SPRINT_SUMMARY.md) — one line per accepted sprint (1–18); see `docs/UX_SPRINT_LOG.md` for full detail.
- [Release Notes v1.0 (DRAFT)](docs/Release_Notes_v1.0_DRAFT.md) — draft summary of UX improvements, governance milestones, and known limitations.
- [Retrospective Engineering Report](docs/RETROSPECTIVE_ENGINEERING_REPORT.md) — a candid, first-person account of the 18-sprint programme from the implementing engineer's perspective: what worked, what didn't, and what to change next time.
- [Known Issues Register](KNOWN_ISSUES.md), [Release Checklist](RELEASE_CHECKLIST.md), [Release Candidate Report](RELEASE_CANDIDATE_REPORT.md) — the independent Sprint 18 release audit: findings, item-by-item verification, and final GO/NO-GO recommendation.

## Pipeline

1. Put source PDFs in `data/input/pdfs/`.
2. Generate draft outlines:

   ```bash
   bookcorpus-outline
   ```

3. Review a generated `data/work/outlines/*_outline.csv` and save the approved
   version as `*_outline_clean.csv`.
4. Extract sections, naming the PDF explicitly when its filename does not match
   the outline stem:

   ```bash
   bookcorpus-extract \
     --outline data/work/outlines/book_outline_clean.csv \
     --pdf data/input/pdfs/book.pdf
   ```

All commands accept explicit input/output paths; their defaults are anchored to
the repository and do not depend on the shell's working directory.

## Important provenance limitation

The legacy `bookcorpus-extract` command still assumes printed page numbers are
physical page numbers. The GUI does not use that unsafe path: its extraction
service requires an approved mapping and records printed pages, physical pages,
and zero-based PDF indices separately. Treat output from the legacy CLI as
unverified until it is migrated to the same preflight service.

See `docs/ARCHITECTURE.md` for the directory contract and `docs/audits/` for the
pre-reorganization technical assessment.
