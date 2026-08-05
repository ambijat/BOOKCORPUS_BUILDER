# BOOKCORPUSBUILDER — Independent Technical Assessment

**Report No.** BCB-2026-08
**Assessment date:** 2026-08-03
**Prior internal audit:** 2026-07-30 (see `../docs/PROJECT_AUDIT_REPORT.md`)
**Method:** Static source review + line-level re-verification against current source
**Overall status:** ⚠️ **Not production-ready**
**Published version:** <https://claude.ai/code/artifact/c89f7c89-993a-43d1-9ed0-16bb8637fa01> (Claude Artifact — private by default; use its share menu before forwarding externally)

---

## Executive summary

BOOKCORPUSBUILDER extracts citable subcorpora — chapter- and section-level text with page provenance — from book-length PDFs, feeding a topic-modeling notebook and an experimental text-to-speech cast. The architecture is sound: separate outline discovery from human review and text extraction, keep printed-page and physical-page coordinates distinct, and let a human correct the outline before any text is cut. **The current code does not implement that design.**

> **Verdict:** The pipeline can complete successfully while silently extracting the wrong pages. There is no offset validation, no test suite, no reproducible environment, no version control, and no downstream consumer for the current output format. Treat all output produced by the current scripts as unverified research material, not citation-grade data, until the findings below are remediated.

This report re-verifies, line-by-line against the current source, a prior internal audit dated 2026-07-30. No file relevant to the findings had changed since that date — the codebase, virtual environment, and directory layout were identical to what was audited. Every critical and high-severity claim below was independently re-derived from the code during this assessment, not carried over unchecked.

### Severity summary

| Severity | Count |
|---|---:|
| Critical | 3 |
| High | 7 |
| Medium | 8 |
| Low | 5 |

---

## Project inventory

The project root occupies roughly 234 MB and is **not under version control** (no `.git`). It holds three overlapping generations of a PDF-to-corpus pipeline plus historical outputs:

| Component | Location | Size / count | Status |
|---|---|---:|---|
| Gen 1 chapter builder | `oldcode/book_subcorpora_builder_v5.py` | 442 lines | Archived |
| Gen 2 chapter builder + dehyphenation | `book_subcorpora_builder_v6.py` | 618 lines | Runnable, superseded |
| Gen 3 outline extractor | `oldcode/pdf_outline_to_csv.py` | 525 lines | Live but filed as archived |
| Gen 3 section extractor | `book_subcorpora_builder_v7.py` | 258 lines | Documented, broken by default |
| TTS narration script | `debate_cast_tts.py` | 95 lines | Runnable, unverified deps |
| Analysis notebook | `subcorpora_IR_template.ipynb` | 1 file | Targets Gen 1/2 output only |
| Python environment | `.venv/` | 154 MB | Interpreter unusable |
| Source PDFs (current) | `pdf/local_books/` | 4 files, 58 MB | Present |
| Archived outputs | `otuput_dump/` | 23 MB | Internally consistent (verified) |
| Live pipeline directories | `contents/`, `chunks/`, `local_books/` | 0 files | Empty |

Documented pipeline: `PDF → outline extraction → human-edited CSV → section extraction → TXT + JSONL + manifest`. As shipped, the outline extractor lives under `oldcode/` and resolves its own paths there, `book_subcorpora_builder_v7.py` points at different top-level folders that are empty, and no reviewed outline or section output currently exists outside the archive — see [C3](#c3).

---

## Critical findings

Defects that can silently corrupt output or block the documented workflow entirely. All three were reproduced by direct code inspection during this assessment.

### C1. Printed page and physical PDF page are treated as identical, with no offset

`book_subcorpora_builder_v7.py:117–136` — `extract_text_pages()` takes a 1-based page number and indexes directly into `pdf.pages`. Its own comment states the assumption: *"start_page/end_page are 1-indexed 'printed pages' == PDF page numbers here."* There is no offset argument, page-label lookup, or separate physical-page field anywhere in the file.

`book_subcorpora_builder_v6.py:344–362` — `infer_printed_offset()` searches the first two words of the first chapter title against the first 40 physical pages and returns the first match, with no exclusion of table-of-contents pages, where the same title text also appears.

**Impact:** A run can complete and print plausible chapter ranges while every extracted section starts on the wrong physical page — inside front matter or several pages early. All downstream TF-IDF terms, topics, clusters, and citations then carry incorrect provenance, and the error is invisible from the command output.

**Required fix:**
- Introduce one shared coordinate model with distinct `printed_page`, `physical_page_number`, and `pdf_page_index` fields.
- Require a user-approved offset or validated page labels — never infer it from a TOC occurrence.
- Persist both coordinate systems in every output record so provenance is auditable after the fact.

### C2. The outline extractor writes two incompatible page-coordinate systems into one CSV column

`oldcode/pdf_outline_to_csv.py:269` — `parse_toc_pages()` stores the page number *printed in the table of contents* as `OutlineItem.printed_start`.

`oldcode/pdf_outline_to_csv.py:367` — the layout-based heading/caption pass stores `printed_start=pi + 1`, i.e. the *physical* PDF page number, in that same field. Both sources are merged, deduplicated, and sorted together at lines 279–392 with no marker for which coordinate system produced a given row.

**Impact:** When TOC parsing succeeds, one exported CSV can mix printed and physical page numbers in the same `printed_start` column. Sorting and end-page computation become mathematically invalid, and the downstream extractor has no way to know how to interpret a given row.

**Required fix:**
- Persist `source`, `kind`, `printed_start`, and `physical_start` as separate fields.
- Never merge candidates whose coordinate system is unresolved.

### C3. The documented Generation 3 workflow does not run from a fresh checkout

`book_subcorpora_builder_v7.py:6–11` (docstring) describes `pdf/local_books/` and `csv/contents/`. The code at lines 39–40 instead uses top-level `local_books/` and `contents/` — both currently empty.

`oldcode/pdf_outline_to_csv.py:25–28` — `BASE_DIR` resolves to the script's own `oldcode/` directory, so the only current outline extractor defaults to `oldcode/local_books/` and `oldcode/contents/`, neither of which is the live project layout described in `ONTOLOGICAL_BASIS.md`.

**Impact:** Following the documented pipeline as written fails at every stage; a user must reverse-engineer manual path overrides before anything runs end to end.

**Required fix:**
- Promote the outline stage out of `oldcode/` and define one project root shared by both stages.
- Add an end-to-end command with explicit, validated input/output arguments (input directories should error, not silently auto-create).

---

## High-severity findings

### H1. The Python environment is not reproducible or directly usable

Re-verified this pass: `file .venv/bin/python .venv/bin/python3` reports both as **data**, not executables — running either fails with `Exec format error` on this filesystem. There is no `pyproject.toml`, `requirements.txt`, lock file, or supported-Python declaration anywhere in the project.

**Recommendation:** delete and recreate the environment from a pinned dependency file; do not version a `.venv` directory at all.

### H2. Outline extraction produces heavy false-positive noise by construction

`oldcode/pdf_outline_to_csv.py:305–311` — the heading threshold is the **per-page** 90th-percentile font size (floored at 12.5pt), which guarantees that relatively large text on nearly every page qualifies as a heading candidate, independent of the page's actual content. The prior audit's dry run against one current PDF produced 41 candidate rows including boilerplate ("This page intentionally left blank"), title-page fragments, and split headings.

**Recommendation:** use document-level typography statistics, repeated header/footer suppression, and length/confidence rules; add a golden-outline regression check per PDF.

### H3. Output writes are non-atomic and stale files survive reruns

`book_subcorpora_builder_v7.py:208–247` — the JSONL file is truncated immediately on open, section text is written incrementally per row, and the manifest is written last, after every other write has completed. Nothing clears `txt_out_dir` before a rerun, so a renamed or removed outline row leaves its old `.txt` file behind. An exception partway through leaves the JSONL, TXT tree, and manifest mutually inconsistent with no marker that the run was incomplete.

**Recommendation:** build into a temporary run directory, validate counts, then atomically promote; give every run an immutable ID.

### H4. A successful exit does not mean complete output

`book_subcorpora_builder_v7.py:168, 211–212` — `--min_chars` defaults to 1 but any row producing shorter text is silently dropped with `continue`; no count of expected vs. written vs. skipped rows is ever printed. `oldcode/pdf_outline_to_csv.py:507–508` — the outline batch loop wraps each PDF in `except Exception as e: print(...)` and continues, so the whole command can still exit 0 after every PDF failed.

**Recommendation:** track expected/written/skipped/failed counts explicitly and return a non-zero exit code on any unrequested partial result.

### H5. No automated tests protect page provenance or text quality

Confirmed this pass: no `tests/` directory, test framework, fixture, or CI configuration exists anywhere in the project (`find . -iname "*test*"` returns nothing outside `.venv`). The single highest-risk code path — printed/physical page conversion — is entirely unverified by automation.

**Recommendation:** minimum coverage should include offset conversion against known page starts, TOC-occurrence vs. body-heading disambiguation, duplicate/non-monotonic starts, and interrupted-write recovery.

### H6. Architecture documentation asserts invariants the code does not implement

`ONTOLOGICAL_BASIS.md:226–231` states that "every stage that deals in page numbers keeps `printed_start`/`printed_end` ... separate" from the actual PDF index "via an explicit offset." Confirmed this pass: `book_subcorpora_builder_v7.py` has no offset parameter, no offset inference call, and no second coordinate field anywhere in the file — see [C1](#c1). The document describes an intended invariant as if it were an implemented one.

**Recommendation:** mark aspirational claims in project docs explicitly as roadmap, not current behavior, until C1 is fixed.

### H7. Current Generation 3 output has no downstream consumer

`subcorpora_IR_template.ipynb:216–217` — the analysis notebook reads `chapter_XX/meta.json` and `chapter_XX/corpus.txt`, the Gen 1/2 chapter-level output shape. It contains no reference to the Gen 3 JSONL, manifest, or per-section TXT files that `book_subcorpora_builder_v7.py` produces. Nothing in the project reads the current pipeline's own output format.

**Recommendation:** choose and document one canonical output contract, then port the notebook to consume it before adding further Gen 3 features.

---

## Medium-severity findings

### M1. Offset inference is collision-prone even outside the TOC

`book_subcorpora_builder_v6.py:349–360` matches only the first two normalized words of the first chapter title anywhere in the first 40 pages and accepts the first hit — generic titles like "Introduction" collide easily. On no match, offset silently defaults to 0.

### M2. Outline CSV input validation is minimal

`book_subcorpora_builder_v7.py:91` sorts rows by `Sno`, not by page start, and never rejects duplicate serial numbers, non-monotonic starts, or negative `--min_chars`. `extract_text_pages():125–126` silently clamps out-of-range page numbers instead of failing, hiding bad metadata.

### M3. Page-range ("end page") logic is duplicated and inconsistent between generations

`book_subcorpora_builder_v7.py:95–114` computes end-of-range as the next *distinct* start minus one. `oldcode/pdf_outline_to_csv.py:397–410` computes it from the immediate next row regardless of whether its start differs. Neither shared code nor a test enforces one rule, so ranges computed at the outline stage and at the extraction stage can diverge.

### M4. PDF extraction reopens the source file once per section

`book_subcorpora_builder_v7.py:192, 210, 123` — the PDF is opened once to count pages, then `extract_text_pages()` reopens it fresh inside the loop for every single outline row. For books with many sections this repeatedly re-parses the same file; the handle should stay open for the run.

### M5. Text-cleanup quality regressed from Gen 2 to Gen 3, and Gen 2's own dehyphenation has edge cases

`book_subcorpora_builder_v7.py` writes raw `pdfplumber` text with no dehyphenation step at all — confirmed by the absence of any such call in the file. Gen 2's `dehyphenate_text()` (`v6.py:112`) matches only a literal space after the hyphen (`- +`), so calling it directly on a raw line-broken string containing `"hyphen-\nated"` will not join the word — it only works correctly because `chunk_paragraphs()` converts newlines to spaces *before* calling it. The wrap-mode hard-wrap loop (`v6.py:186–197`) can also emit an empty chunk when a single word exceeds the configured width.

### M6. The analysis notebook mutates the runtime environment and targets a nonexistent path

`subcorpora_IR_template.ipynb:64,71` — cells call `subprocess.check_call([sys.executable, "-m", "pip", "install", ...])` for `nltk` and `scikit-learn` at run time, plus `nltk.download(...)` calls, making execution non-deterministic and network-dependent. Line 35 configures `BASE_DIR = "./book3_subcorpora_v5"`, which does not exist anywhere in the current project (the corresponding archive is `otuput_dump/book3_subcorpora/`).

### M7. TTS script has a path-relative design, a cleanup bug, and a non-fatal conversion failure

All output paths in `debate_cast_tts.py` are relative to the caller's working directory, not the script location. In `try_espeak_cli_wav()` (lines 44–62), when neither `espeak-ng` nor `espeak` is found on `PATH`, the function `return`s at line 51 — before reaching the `try/finally` block that deletes `tmp_es_input.txt`, so the temp file is left behind on that failure path. `maybe_convert_to_mp3()` (lines 64–76) catches and prints on `ffmpeg` failure but returns normally either way; `main()` never checks the return value, so an MP3 conversion failure does not fail the command.

### M8. No data governance documentation for the source corpus

The project bundles four named, copyrighted political-theory books plus derived text and audio, with no provenance ledger, license or permission notes, retention policy, or redistribution guidance anywhere in the repository. Corpus extraction of this kind can carry copyright and research-data obligations independent of whether the code runs correctly.

---

## Low-severity findings

| ID | Finding | Evidence |
|---|---|---|
| L1 | No repository or release metadata | Confirmed — `git status` reports "not a git repository"; no commit history, tags, or branches exist. |
| L2 | No README, license, or quick start | Confirmed — no `README*` or `LICENSE*` file anywhere in the project root. |
| L3 | Generated and source artifacts poorly separated | The archive directory is misspelled `otuput_dump`; IDE state (`.idea/`) and a 154 MB environment sit beside source; overlapping script names/directories span three generations. |
| L4 | Output schema is inconsistent between sibling files | Confirmed — the JSONL record uses lowercase `"sno"` while the manifest CSV header uses `"Sno"`. The manifest also stores the machine-specific absolute path `/media/ambijat/SOPRANO2/…` with no content hash, source-PDF hash, tool version, or timestamp. |
| L5 | General code hygiene | Confirmed — a bare `except: pass` at `debate_cast_tts.py:62`, broad `except Exception` handlers in multiple files, and no consistent formatter/linter configuration. No hardcoded credentials or API secrets were found in a project-wide pattern scan. |

---

## Validation performed

Every check below was executed directly against the current source during this assessment (2026-08-03), not inherited from the prior audit without confirmation.

| Check | Result |
|---|---|
| Codebase changed since the 2026-07-30 internal audit? | ✅ No — all relevant file mtimes precede the audit date |
| Git repository present | ❌ No — "not a git repository" at project root |
| `.venv/bin/python` / `python3` executable | ❌ No — both report as `data`, not a binary/symlink |
| Python line count across 5 project scripts | ✅ 1,938 total — exact match (618+258+442+525+95) |
| Archived chapter outputs: `meta.json` count | ✅ 26 files, matched 1:1 with `corpus.txt` |
| Archived analysis CSVs readable | ✅ 9 files; `paragraphs_raw.csv` = 618 data rows |
| JSONL vs. manifest field-name consistency | ❌ Confirmed mismatch — `sno` vs. `Sno` |
| Manifest path portability | ❌ Confirmed — absolute, machine-specific path stored per row |
| Notebook runtime package installation | ❌ Confirmed — `pip install` via `subprocess.check_call` for nltk, scikit-learn |
| Notebook default input path exists | ❌ No — `./book3_subcorpora_v5` not present in project |
| `tests/` directory or CI configuration | ❌ None found |
| README / LICENSE present | ❌ Neither present |
| Credential / secret pattern scan across source | ✅ No matches |

---

## Remediation plan (summary)

Full checklist form with per-item findings references: `../docs/IMPROVEMENT_ROADMAP.md`.

- **Phase 0 — Stop silent corruption:** fix the printed/physical page coordinate model; require a validated offset; exclude TOC pages from inference. *(C1, C2)*
- **Phase 1 — Make one workflow runnable:** promote the outline stage out of `oldcode/`; add `pyproject.toml` + lock file + README; recreate `.venv`; initialize Git. *(C3, H1, L1, L2)*
- **Phase 2 — Establish output integrity:** validate outlines; make writes atomic and run-scoped; add hashes/versions/timestamps to manifests; make partial completion explicit. *(H3, H4, M2, M3, L4)*
- **Phase 3 — Add quality gates:** synthetic PDF fixtures with known offsets; golden outlines; CI for tests/lint/schema. *(H2, H5, M4)*
- **Phase 4 — Restore the downstream value chain:** port the notebook to canonical Gen 3 output; pin NLP resources; fix TTS path/cleanup bugs; document source-PDF rights. *(H7, M5, M6, M7, M8)*

---

## Acceptance criteria for a reliable release

- [ ] A clean environment builds from one documented command.
- [ ] The full pipeline runs from a fresh checkout with no manual path surgery.
- [ ] Printed page 3 of the audited Marcuse/Arendt PDF resolves to its true body-page location, not its earlier table-of-contents occurrence.
- [ ] Every section record stores validated printed *and* physical page ranges.
- [ ] A failed or partial run cannot exit as if it had succeeded.
- [ ] Tests cover coordinate conversion, duplicate/non-monotonic starts, and interrupted writes.
- [ ] At least one downstream analysis consumes the canonical Gen 3 output format.
- [ ] Source-document rights and redistribution expectations are written down.

---

## Bottom line

The project's core idea — separating outline discovery, human review, and section extraction while keeping printed and physical page coordinates distinct — is sound and partially demonstrated by the archived Gen 1/2 outputs. It is not currently guaranteed by the code that runs today. Fix page provenance first (Phase 0); packaging, atomicity, tests, and downstream integration should follow in that order before any output is treated as citation-grade.

---

*BOOKCORPUSBUILDER · Independent Technical Assessment · Prepared 2026-08-03 · Re-verifies internal audit of 2026-07-30*
