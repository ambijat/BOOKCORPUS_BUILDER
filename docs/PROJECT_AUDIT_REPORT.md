# BOOKCORPUSBUILDER Project Audit

> Historical snapshot: findings describe the pre-reorganization layout.
> Current locations and resolved architecture items are documented in
> `ARCHITECTURE.md`; the original polished assessment is under `audits/`.

**Audit date:** 2026-07-30  
**Scope:** Project structure, Python scripts, notebooks, documentation, dependencies, source PDFs, generated artifacts, testability, data integrity, security, and maintainability.  
**Audit method:** Read-only source review plus isolated smoke tests in temporary directories. No production corpus outputs were changed.

**Formatted version for forwarding:** re-verified and republished as a polished report on 2026-08-03 — <https://claude.ai/code/artifact/c89f7c89-993a-43d1-9ed0-16bb8637fa01> (Claude Artifact, private by default; use its share menu to grant access). Markdown copy: `audits/BOOKCORPUSBUILDER_Technical_Assessment_2026-08-03.md`. Phased remediation checklist: `IMPROVEMENT_ROADMAP.md`.

## Executive assessment

**Overall status: proof of concept; not reliable for unattended corpus production.**

The project has a useful architectural idea: separate outline discovery from human review and section extraction, while retaining an older chapter-level pipeline and a demonstrated analysis notebook. The archived outputs prove that useful corpora and topic-analysis artifacts have been produced before.

The current Generation 3 workflow is not end-to-end runnable with its defaults, and both current extraction paths can silently select the wrong PDF pages. This is the highest-risk defect because a run may complete successfully while producing semantically incorrect corpora. Reproducibility is also weak: there is no usable environment definition, test suite, CI, Git metadata, README, or run manifest.

### Severity summary

| Severity | Count | Meaning |
|---|---:|---|
| Critical | 3 | Can silently corrupt the corpus or prevents the documented workflow |
| High | 7 | Major reliability, reproducibility, or output-integrity weakness |
| Medium | 8 | Material maintainability, quality, or operational issue |
| Low | 5 | Hygiene and consistency issue |

### Recommended decision

Do not use the current v6/v7 output as citation-grade data until page-coordinate handling is fixed and validated against known page starts. Preserve the current PDFs and archived outputs, but treat them as research artifacts rather than reproducible build products.

## Project inventory

The folder occupies approximately **234 MB**:

- `.venv/`: approximately 154 MB; packages are present, but its interpreter launchers are unusable.
- `pdf/local_books/`: four current political-theory PDFs, approximately 58 MB total.
- `otuput_dump/`: approximately 23 MB of archived PDFs, chapter corpora, analysis CSVs, and audio.
- Five Python scripts: 1,938 lines total, including two under `oldcode/`.
- Two notebooks, three Freeplane mind maps, two PNG diagrams, and three architectural Markdown documents.
- Current `contents/`, `chunks/`, and top-level `local_books/` directories are empty.

The current conceptual pipeline is:

```text
PDF -> outline extraction -> human-edited CSV -> section extraction
    -> TXT + JSONL + manifest
```

In practice, the outline extractor is under `oldcode/`, its defaults point inside that folder, v7 points to different empty folders, and no current reviewed outlines or section outputs exist.

## Critical findings

### C1. Both extraction generations can silently map printed pages to the wrong physical PDF pages

**Evidence**

- `book_subcorpora_builder_v7.py::extract_text_pages()` explicitly assumes that a 1-based “printed page” equals a 1-based physical PDF page. There is no offset argument, inference, page-label lookup, or separate actual-page field.
- `book_subcorpora_builder_v6.py::infer_printed_offset()` searches for the first two words of the first chapter title in the first 40 physical pages. It does not exclude table-of-contents pages.
- In an audit dry run on `Politics As Radical Creation _Marcuse and Hannah.pdf`, v6 parsed 11 TOC entries and inferred offset `3`. It mapped printed page 3 to physical page 6. Physical page 6 is the table of contents; the actual Introduction begins on physical page 12, requiring offset `9`.
- The command exited successfully and reported plausible chapter ranges, so this defect is silent.

**Impact**

Chapter and section text can start in front matter or end several pages early. All derived TF-IDF terms, topics, clusters, summaries, retrieval results, and citations then inherit incorrect provenance.

**Required fix**

Create one shared page-coordinate model with distinct fields for:

- `printed_page`
- `physical_page_number` (1-based)
- `pdf_page_index` (0-based)
- `offset` and how it was established

Require either a user-approved offset, trustworthy PDF page labels, or validation against body-page headings. Never infer the offset from TOC occurrences. Store both printed and physical start/end values in every output record.

### C2. The outline extractor mixes two page-coordinate systems in one field

**Evidence**

- `oldcode/pdf_outline_to_csv.py::parse_toc_pages()` stores page numbers printed in the TOC as `OutlineItem.printed_start`.
- `extract_outline_from_pdf()` also stores layout candidates using `pi + 1`, which is the physical PDF page number, in that same `printed_start` field.
- It merges, sorts, deduplicates, ranges, and exports both sources together without recording their source or converting between coordinates.

**Impact**

When TOC parsing succeeds, one CSV column can contain both printed and physical page numbers. Sorting and `printed_end` calculation become invalid, and v7 cannot know how to interpret a row.

**Required fix**

Persist `source`, `kind`, `printed_start`, and `physical_start` separately. Convert only after an offset has been explicitly established. Do not merge candidates that have unresolved coordinate systems.

### C3. The documented Generation 3 workflow is broken by default

**Evidence**

- v7’s docstring describes `pdf/local_books/` and `csv/contents/`, but code uses top-level `local_books/` and `contents/`. The top-level `local_books/` directory is empty.
- The outline extractor’s `BASE_DIR` is its own `oldcode/` directory, so defaults resolve to `oldcode/local_books/` and `oldcode/contents/`, neither of which represents the live project layout.
- `ensure_dirs()` creates a missing source directory, which can conceal a bad path.
- The only outline extractor is filed under `oldcode/`, while current documentation calls it the live Stage 1.
- Current `contents/` and `chunks/` contain no files.

**Impact**

The pipeline cannot be followed as documented. Users must discover and supply manual path overrides at every stage.

**Required fix**

Move the live outline stage out of `oldcode/`, define one project root and one configuration contract, and add an end-to-end command that uses explicit input/output arguments. Input directories must be validated, not created.

## High-severity findings

### H1. The Python environment is not reproducible or directly usable

- `.venv/bin/python`, `python3`, and `python3.12` are `IntxLNK` data stubs rather than executable symlinks on this filesystem; direct execution fails with `Exec format error`.
- Pip launchers point to the broken interpreter.
- The host Python lacks `pdfplumber`, `PyMuPDF`, `pyttsx3`, and NLTK.
- Packages could be imported only by manually injecting `.venv/lib/python3.12/site-packages` into `PYTHONPATH`.
- There is no `pyproject.toml`, `requirements.txt`, lock file, supported Python version declaration, or environment setup guide.

**Recommendation:** Delete and recreate the environment after adding a pinned dependency specification. Do not distribute or version a `.venv` directory.

### H2. Outline extraction produces substantial false positives

An isolated run on `Politics As Radical Creation _Marcuse and Hannah.pdf` produced 41 outline rows, including:

- “This page intentionally left blank”
- title-page fragments
- `contents`
- prose sentences incorrectly classified as chapter headings
- split headings represented as separate sections

The per-page 90th-percentile font threshold guarantees that relatively large text on almost every page can become a candidate. The result needs extensive manual correction before it is safe to use.

**Recommendation:** Use document-level typography statistics, stronger heading features, repeated-header/footer removal, minimum/maximum length rules, and confidence scores. Add golden-outline evaluation for every current PDF.

### H3. Output writes are non-atomic and stale files survive reruns

v7 truncates the JSONL before extraction, writes section text incrementally, and writes the manifest last. An exception can leave mutually inconsistent outputs. It does not clear or reconcile old section TXT files, so removed/renamed outline rows leave stale files behind.

**Recommendation:** Build in a temporary run directory, validate counts and hashes, then atomically promote the completed run. Give each run an ID and immutable manifest.

### H4. “Success” does not guarantee complete output

- v7 silently drops sections shorter than `--min_chars`; the smoke test dropped the blank first section and emitted only the second row while printing `Done`.
- It does not report expected, written, skipped, or failed counts.
- The outline batch catches every per-PDF exception, prints an error, and can still exit successfully after failures.
- Empty outlines and zero written chunks are not fatal.

**Recommendation:** Add explicit counts, skip reasons, validation thresholds, and nonzero exit codes for incomplete runs unless partial output was explicitly requested.

### H5. No automated tests protect page provenance or text quality

There is no `tests/` directory, test framework configuration, CI workflow, or fixture set. Python syntax compilation succeeds, but the critical semantic paths are untested.

Minimum tests should cover:

- printed/physical/index conversions and known offsets
- TOC-title occurrence versus true body-heading occurrence
- duplicate and non-monotonic starts
- multiple rows sharing a start
- blank/scanned pages
- interrupted/partial writes
- dehyphenation and paragraph wrapping
- expected outlines for small synthetic PDFs

### H6. Existing architectural documentation contains incorrect assurances

`ONTOLOGICAL_BASIS.md` states that every page-number stage keeps printed and actual coordinates separate. v7 does not. It also describes `oldcode/pdf_outline_to_csv.py::add_page_ranges()` and v7 range handling as equivalent, but they differ for repeated starts. `ATTRIBUTES.md` recognizes path mismatches but understates that the outline extractor resolves paths relative to `oldcode/`.

**Recommendation:** Update the documents after the coordinate contract is fixed. Mark current claims as intended invariants, not implemented invariants.

### H7. Current Generation 3 outputs have no downstream consumer

The analysis notebook reads `chapter_XX/corpus.txt` plus `meta.json`; it does not read v7 JSONL, manifests, or section TXT files. The TTS script consumes a hand-written debate script. No code in the project consumes current section records.

**Recommendation:** Choose and document the canonical output contract, then port one analysis path to it before expanding deliverables.

## Medium-severity findings

### M1. v6 offset inference is weak even after excluding TOC pages

It matches only the first two normalized title words within the first 40 pages and accepts the first substring match. Generic titles such as “Introduction” are collision-prone. When inference fails, offset silently defaults to zero.

### M2. Input validation is insufficient

v7 sorts outlines by `Sno`, not page start, and does not reject duplicate serial numbers, non-monotonic starts, starts past the document, empty outlines, negative `--min_chars`, or slug collisions. Page numbers beyond the PDF are silently clamped, hiding bad metadata.

### M3. Range semantics are duplicated and inconsistent

The “next distinct start minus one” logic exists in multiple scripts. The old outline extractor uses the immediate next item and clamps, while v7 searches for the next greater start. Neither shared code nor tests enforce one rule.

### M4. PDF extraction is unnecessarily expensive

v7 reopens the full PDF once to count pages and again for every section. With many sections or large books, this repeatedly parses the same file. The PDF should remain open for the run.

### M5. Text cleanup regressed in v7

v7 writes raw `pdfplumber` text and drops v6 dehyphenation without an explicit policy. v6 itself has edge cases: direct `dehyphenate_text("hyphen-\\nated")` does not join the word, and wrap mode can emit an empty chunk when a single word exceeds the configured width.

### M6. The notebook performs network and environment mutation at runtime

`subcorpora_IR_template.ipynb` installs missing packages and downloads NLTK resources inside cells. This is unsuitable for offline, deterministic, or reviewed execution. Its configured input `./book3_subcorpora_v5` does not exist in the current root.

### M7. TTS has path, cleanup, and status weaknesses

All paths are relative to the caller’s working directory rather than the script. If no espeak executable exists, `tmp_es_input.txt` is left behind because the function returns before its cleanup block. MP3 conversion failure does not make the overall command fail.

### M8. Data governance is undocumented

The project contains four named books and archived PDFs/audio, but no provenance ledger, license/permission notes, retention policy, or redistribution guidance. Corpus extraction can implicate copyright and research-data obligations even when technically successful.

## Low-severity findings

### L1. Repository and release metadata are absent

The folder is not a Git repository and has no commit history, tags, branches, or auditable change provenance.

### L2. Essential project documentation is missing

There is no README, license, contribution guide, security policy, changelog, or runnable quick start.

### L3. Generated and source artifacts are poorly separated

The archive folder is misspelled `otuput_dump`; IDE state and a full environment live beside source; current and historical scripts use overlapping names and directories.

### L4. Output schemas are inconsistent

JSONL uses `sno`; the sibling manifest uses `Sno`. Manifests store machine-specific absolute paths and no content hashes, tool version, timestamp, source-PDF hash, extraction library version, or review status.

### L5. General code hygiene needs attention

There are broad exception handlers, one bare `except`, unused imports, compressed multi-statement formatting in TTS, and no consistent formatter/linter configuration. No hardcoded credentials or API secrets were detected in project source.

## Validation performed

| Check | Result |
|---|---|
| Python syntax compile of all five `.py` files | Passed with host Python 3.12 |
| v6 `--help` | Passed |
| v7 `--help` with host Python | Failed: missing `pdfplumber` |
| Outline extractor `--help` with host Python | Failed because dependency import occurs inside `main()` before argument handling |
| TTS smoke run | Failed: neither `pyttsx3` nor espeak available |
| v6 isolated dry run with manually exposed packages | Completed, but inferred the demonstrably wrong page offset |
| v7 isolated two-row smoke run | Completed; one blank row was silently omitted |
| Outline isolated smoke run on one current PDF | Completed; 41 noisy candidates |
| Archived chapter output consistency | 26 metadata files, all with matching `corpus.txt`; page-count arithmetic internally consistent |
| Archived analysis CSV readability | Nine CSVs readable; 618 paragraph rows in both raw and enriched tables |
| Secret-pattern scan | No credentials found |
| Dependency health | No project lock/specification; shared environment reports unrelated broken requirements |

The smoke tests used temporary output directories. Temporary files generated during auditing were moved to the desktop trash after inspection.

## Remediation plan

### Phase 0 — Stop silent corruption

1. Freeze citation-grade production runs.
2. Define and test the printed/physical/index coordinate model.
3. Add `--printed-offset` or verified page-label mapping to v7.
4. Prevent offset inference from matching TOC/front-matter occurrences.
5. Store both coordinate systems in outline, JSONL, manifest, and TXT metadata.
6. Fail on unresolved or unvalidated page mapping.

### Phase 1 — Make one workflow runnable

1. Promote the outline extractor from `oldcode/`.
2. Create `pyproject.toml` plus a lock file and supported Python declaration.
3. Add a README with one end-to-end command sequence.
4. Consolidate paths under explicit CLI/config arguments.
5. Recreate `.venv`; exclude environments, IDE state, outputs, and copyrighted source data from version control as appropriate.
6. Initialize Git after deciding what data may be tracked.

### Phase 2 — Establish output integrity

1. Add schema validation and strict outline checks.
2. Introduce atomic, run-scoped output directories.
3. Add source and output SHA-256 hashes, timestamps, tool/library versions, review state, and counts.
4. Detect stale files and filename collisions.
5. Make partial completion explicit and machine-detectable.

### Phase 3 — Add quality gates

1. Build synthetic PDF fixtures with known printed/physical offsets.
2. Create hand-approved golden outlines for at least two current PDFs.
3. Test text extraction and dehyphenation edge cases.
4. Add CI for tests, formatting, linting, and schema validation.
5. Measure outline precision/recall rather than relying solely on manual inspection.

### Phase 4 — Restore the downstream value chain

1. Port the notebook logic into a deterministic script that consumes the canonical section JSONL.
2. Pin NLP models/resources and remove runtime package installation.
3. Add traceable links from derived terms/topics/summaries back to section IDs and page coordinates.
4. Connect TTS only after generated scripts retain citations to corpus sections.

## Acceptance criteria for a reliable release

A release candidate should not be considered reliable until:

- a clean environment can be created from one documented command;
- a complete pipeline runs from a fresh checkout without manual path surgery;
- printed page 3 of the audited Marcuse/Arendt PDF maps to physical page 12, not its TOC occurrence on page 6;
- every section record stores validated printed and physical ranges;
- failures cannot leave a run appearing complete;
- expected and actual record counts match or skips are explicitly approved;
- tests cover coordinate conversion, blank pages, duplicates, interrupted writes, and outline quality;
- at least one downstream analysis consumes the canonical current output;
- source-document rights and redistribution expectations are documented.

## Bottom line

The project demonstrates a promising research workflow and retains useful historical outputs, but its most important claim—page-grounded, citable subcorpora—is not currently guaranteed by the code. Correct page provenance first; environment, packaging, output atomicity, tests, and downstream integration should follow in that order.
