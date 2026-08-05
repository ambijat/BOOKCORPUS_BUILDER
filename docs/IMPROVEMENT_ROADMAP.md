# Improvement Roadmap — BOOKCORPUSBUILDER

Derived from the independent technical assessment of 2026-08-03 (re-verifying
the internal audit of 2026-07-30). Findings are cited as `C#`/`H#`/`M#`/`L#`;
full evidence for each lives in `PROJECT_AUDIT_REPORT.md`.

Phases are ordered by dependency, not just severity: later phases assume
earlier ones are done, so do not start Phase 2 work on top of an unfixed
Phase 0 page-offset bug — it just produces well-packaged wrong output.

---

## Phase 0 — Stop silent corruption

The pipeline can currently report success while extracting text from the
wrong physical PDF pages. Nothing downstream is trustworthy until this is
closed.

- [ ] Freeze citation-grade production runs until page provenance is fixed.
- [ ] Define one shared coordinate model with distinct `printed_page`,
      `physical_page_number`, and `pdf_page_index` fields. *(C1, C2)*
- [ ] Require a user-approved `--printed-offset` or a verified page-label
      mapping; refuse to run without one instead of defaulting to an
      inferred or zero offset. *(C1)*
- [ ] Exclude table-of-contents / front-matter pages from offset inference
      entirely — matching a chapter title's first words against the first
      40 pages currently matches its own TOC entry. *(C1, M1)*
- [ ] Persist `source`, `kind`, `printed_start`, and `physical_start` as
      separate fields in outline output; never merge candidates whose
      coordinate system is unresolved. *(C2)*

## Phase 1 — Make one workflow runnable

The path and layout blockers in this phase were addressed by the 2026-08-03
reorganization. Reproducible locking and version-control initialization remain.

- [x] Promote the outline extractor into `src/bookcorpusbuilder/` and give
      both live stages the shared path contract in `paths.py`. *(C3)*
- [x] Reconcile command documentation and defaults around `data/input/pdfs`,
      `data/work/outlines`, and `data/output`. *(C3)*
- [ ] Add `pyproject.toml` plus a lock file and a declared supported Python
      version. *(H1)*
- [x] Write a README with an end-to-end command sequence. *(L2)*
- [ ] Recreate `.venv` from the pinned spec; the current one has broken
      interpreter symlinks and should not be distributed. *(H1)*
- [ ] Decide what belongs in version control (exclude `.venv/`, `.idea/`,
      generated outputs, and copyrighted source PDFs as appropriate), then
      initialize Git. *(L1)*

## Phase 2 — Establish output integrity

Once a run can complete correctly, make sure a completed run is trustworthy
and inspectable after the fact.

- [ ] Add outline validation: reject duplicate `Sno`, non-monotonic starts,
      and out-of-range page numbers instead of silently clamping. *(M2)*
- [ ] Reconcile the two different "end of range" formulas (next *distinct*
      start vs. immediate next row) between the outline and extraction
      stages into one shared implementation. *(M3)*
- [ ] Make output writes atomic and run-scoped: build into a temp directory,
      validate, then promote — no more truncate-then-incrementally-write
      against the live output tree. *(H3)*
- [ ] Detect and remove stale per-section `.txt` files left behind by
      renamed/removed outline rows on rerun. *(H3)*
- [ ] Track and print expected / written / skipped / failed counts; exit
      non-zero on any unrequested partial result. *(H4)*
- [ ] Add source-PDF hash, output hash, tool version, and timestamp to every
      manifest row; drop machine-specific absolute paths. *(L4)*
- [ ] Unify the `sno`/`Sno` field-name mismatch between the JSONL and
      manifest schemas. *(L4)*

## Phase 3 — Add quality gates

No automated test exists for the single highest-risk code path (page
provenance) or for outline quality.

- [ ] Build synthetic PDF fixtures with known printed/physical offsets and
      test the coordinate-conversion logic against them.
- [ ] Add tests for duplicate starts, non-monotonic starts, blank/scanned
      pages, and interrupted/partial writes. *(H5)*
- [ ] Hand-approve golden outlines for at least two current PDFs and measure
      outline precision/recall against them instead of relying on manual
      inspection. *(H2)*
- [ ] Add CI to run tests, formatting, linting, and schema validation on
      every change.
- [ ] Fix the PDF being reopened once per section during extraction while
      test coverage is being added for that code path. *(M4)*

## Phase 4 — Restore the downstream value chain

The analysis notebook and TTS script currently don't connect to the current
pipeline's own output.

- [ ] Port `subcorpora_IR_template.ipynb` off the Gen 1/2 `corpus.txt` /
      `meta.json` shape onto the canonical Gen 3 JSONL output. *(H7)*
- [ ] Remove runtime `pip install` / `nltk.download` calls from the
      notebook; pin NLP resources instead. *(M6)*
- [x] Fix the notebook's default `BASE_DIR`; it now points to the preserved
      historical corpus under `archive/output_dump/`. *(M6)*
- [ ] Restore text-cleanup parity: Gen 3 extraction currently writes raw
      `pdfplumber` text with no dehyphenation step at all. *(M5)*
- [ ] Fix `debate_cast_tts.py`: make output paths relative to the script
      rather than the caller's working directory, clean up
      `tmp_es_input.txt` on the early-return failure path, and make MP3
      conversion failure fail the command. *(M7)*
- [ ] Document source-PDF rights and redistribution constraints before any
      derived corpus leaves the project. *(M8)*

---

## Acceptance criteria — when to call this "reliable"

A release candidate should not be considered reliable until all of the
following hold:

- [ ] A clean environment builds from one documented command.
- [ ] The full pipeline runs from a fresh checkout with no manual path
      surgery.
- [ ] Printed page 3 of the audited Marcuse/Arendt PDF resolves to its true
      body-page location, not its earlier table-of-contents occurrence.
- [ ] Every section record stores validated printed *and* physical page
      ranges.
- [ ] A failed or partial run cannot exit as if it had succeeded.
- [ ] Tests cover coordinate conversion, duplicate/non-monotonic starts, and
      interrupted writes.
- [ ] At least one downstream analysis consumes the canonical Gen 3 output
      format.
- [ ] Source-document rights and redistribution expectations are written
      down.

---

*Full findings, evidence, and severity rationale: `PROJECT_AUDIT_REPORT.md`.
Architectural intent this roadmap must preserve: `ONTOLOGICAL_BASIS.md`.*
