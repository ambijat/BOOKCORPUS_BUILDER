# BOOKCORPUSBUILDER

## Turn books into governed, searchable section corpora

BOOKCORPUSBUILDER is a local-first PySide6 desktop application for converting
PDF books into reviewed, page-aligned and auditable text collections. It keeps
human judgment at the centre of structure creation while automating the
repetitive work of parsing, validation, extraction and retrieval.

Version 0.2.1 adds a spreadsheet-like inspection workbench: visible draggable
column dividers, frozen identifiers, saved widths/order/visibility, header
menus, double-click and toolbar best-fit, Shift-wheel horizontal scrolling, and
persistent adjustable PDF/reference panes.

> **Open book → create structure → review → align pages → approve → extract → search**

## Why it exists

A PDF page number, a printed page number and an internal PDF index are not the
same coordinate. A generated heading is not automatically a trustworthy
boundary. BOOKCORPUSBUILDER makes these distinctions explicit so a useful
outline does not silently become a damaged corpus.

| **Common problem** | **BOOKCORPUSBUILDER response** |
|--------------------|--------------------------------|
| Copied TOCs are inconsistent | Deterministic paste parsing with editable candidate preview |
| JSON metadata is mistaken for titles | Native structured JSON and strict contract import |
| Generated headings look authoritative | Verbatim and analytical structures have different boundary permissions |
| PDF and printed pages do not align | Verified anchors, offsets and explicit irregular exceptions |
| An outline changes after approval | Hash-bound approval is invalidated by edits |
| Extraction results are difficult to audit | Run-scoped TXT, JSONL, manifest and history records |

## A document-centred workflow

1. Add or select a PDF book.
2. Copy its Table of Contents or prepare a structured outline.
3. Paste text, import CSV/JSON, detect from PDF, build manually, or optionally
   generate a local Ollama candidate.
4. Review every candidate beside the PDF reference.
5. Approve the canonical outline.
6. Verify printed-to-physical page mapping.
7. Pass preflight and extract the corpus.
8. Search locally and inspect run history.

Nothing moves directly from generation to extraction.

## One strict outline contract

`book_outline_contract` v1.0.0 is the authoritative Python/JSON interchange
format. Its generated JSON Schema governs GUI import, optional local generation,
staged contract files and validation.

The contract separates:

- document identity and PDF SHA-256;
- generation method and source scope;
- printed, physical and zero-based PDF coordinates;
- entry IDs, source serials and parent hierarchy;
- boundary status and extraction permission;
- verbatim versus analytical provenance;
- confidence, warnings and human review status;
- validation, mapping, approval and payload hash.

Unknown contract fields are rejected. Parent references, hierarchy levels,
coordinate relationships, source evidence and approval hashes are checked
deterministically.

## Analytical insight without unsafe boundaries

Printed structure can be extraction-enabled after review:

```text
kind: chapter
provenance: verbatim
boundary: verified_printed
allow_extraction: true
```

Interpretive structure remains useful metadata by default:

```text
kind: analytical_section
provenance: analytical
boundary: proposed
allow_extraction: false
include: false
```

An analytical row cannot become an extraction boundary merely because a model
or imported file marks it as important.

## Optional local Ollama assistance

The **Generate with Ollama…** action uses the same generated JSON Schema and
authoritative selected-book identity. Output must remain an unvalidated draft
candidate and enters the normal preview.

Ollama cannot:

- approve an outline;
- verify page mapping;
- bypass deterministic validation;
- start extraction; or
- replace human review.

The optional integration is local and is not required for deterministic paste,
CSV, JSON, manual or PDF-detection workflows.

## Built for accountable research

- Source PDFs are treated as read-only.
- Book identity is derived from SHA-256.
- Approved outlines are protected from silent replacement.
- Editing invalidates prior approval.
- Mapping needs two consistent normal anchors.
- Extraction is blocked by invalid or unverified boundaries.
- Successful outputs are promoted atomically into unique run folders.
- Completed, failed and cancelled attempts are recorded.
- Corpus search remains local.

## Verified demonstration

The included Mackinder acceptance example uses a 196-entry outline for
*Democratic Ideals and Reality*:

| **Result** | **Verified value** |
|------------|--------------------|
| Contract entries retained | 196 |
| Verbatim chapters enabled | 8 |
| Analytical metadata disabled | 188 |
| Preflight | Passed |
| TXT / JSONL / manifest records | 8 / 8 / 8 |
| Skipped / failed | 0 / 0 |
| Search for “Heartland” | 4 chapter-level results |

The book contains four pagination discontinuities. The demonstration records
the real chapter mappings instead of forcing an inaccurate global offset.

## Corpus deliverables

Every successful run can provide:

- one UTF-8 TXT file per included section;
- one JSONL collection with text and source coordinates;
- one CSV manifest with paths, hashes and boundaries;
- one immutable run-history record; and
- searchable local results linked back to their source and output files.

## Designed for

- humanities and social-science researchers;
- digital archive and corpus teams;
- editors preparing structured book datasets;
- research assistants handling long-form PDFs; and
- anyone who needs reproducible section-level extraction rather than arbitrary
  page splitting.

## Getting started

```bash
cd /media/ambijat/SOPRANO2/GPT_workflow/BOOKCORPUSBUILDER
../BOOKCORPUSBUILDER-gui-venv/bin/bookcorpus-gui
```

Optional Ollama support:

```bash
pip install -e '.[gui,ollama]'
```

For complete procedures, validation rules and the verified demonstration, see
`BOOKCORPUSBUILDER_Operator_Manual_v0.2.1.docx`.

---

**Schema authority:** Python  
**Validation authority:** Deterministic services  
**Approval authority:** Human operator  
**Execution authority:** Approved, mapped and hash-bound structure
