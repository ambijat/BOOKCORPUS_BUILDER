# Attributes — BOOKCORPUSBUILDER

Verified against current code (Generation 3 / live project). Cross-references:
`ONTOLOGICAL_BASIS.md` (entity definitions), `DIRECTION_OF_REFINEMENT.md`
(roadmap fed by the gaps below).

## Sources of truth, in order of authority

1. **Domain model** — the dataclasses actually constructed
   (`Row`/`ChapterDef`/`OutlineItem`) and the dict shapes written to JSON/CSV.
2. **Storage contract** — the CSV headers and JSONL keys actually written
   (`data/work/outlines/*_outline.csv`, `data/output/manifests/*_manifest.csv`,
   `data/output/jsonl/*_sections.jsonl`, `*/meta.json`).
3. **Docstrings/comments** — useful for intent, but shown below to actively
   disagree with the code in at least one place (Gap 1); code wins.

Repository defaults are centralized in `src/bookcorpusbuilder/paths.py`.
Commands accept explicit locations for use outside the repository.

## Conventions

- **Book identity**: filename stem (`Path.stem`), e.g. `"chapter1"` or
  `"The Human Condition (1958) -- Hannah Arendt"`. No hash, no id field —
  two PDFs with the same stem in different folders are indistinguishable to
  every script here.
- **`Sno`**: 1-based row order within one Book's outline, assigned by
  `enumerate(..., start=1)` after sorting; not stable across a re-extraction
  of the same PDF if the outline detector's output order changes.
- **Section text filenames**: `data/output/sections/<pdf_stem>/{Sno:03d}_{slugify(title)}.txt`
  — `slugify()` lowercases, maps em/en dashes to `-`, strips bracketed tags
  like `[MAP]`, replaces non-alphanumerics with `_`, truncates to 80 chars.
- **Timestamps**: none. Unlike `my_research_assistant`, no output filename or
  record carries a run timestamp — rerunning a stage overwrites the previous
  output tree for that Book in place, with no history retained.
- **Mutability**: `data/work/outlines/<stem>_outline.csv` (machine output) and
  `data/work/outlines/<stem>_outline_clean.csv` (hand-edited) are two distinct files by
  convention (the `_clean` suffix), not two states of one file — but nothing
  enforces that a human actually edited the clean copy; it could be an
  untouched duplicate.
- **Page-range convention**: `printed_end = next distinct printed_start - 1`,
  or `max_page` for the last row — identical formula independently
  implemented three times (`add_page_ranges` in `pdf_outline_to_csv.py`,
  `compute_page_ranges` in `book_subcorpora_builder_v7.py`, and inline logic
  in `chapters_from_seeds`/`chapters_by_regex` in `book_subcorpora_builder_v6.py`).

## Entity field tables

### ChapterDef (`book_subcorpora_builder_v5.py`, `v6.py`)

| Field | Type | Notes |
|---|---|---|
| title | str | from CSV, TOC parse, or regex/bin fallback |
| start_page_idx, end_page_idx | int | 0-based, inclusive, actual PDF index |
| printed_start | Optional[int] | None when seeded by regex fallback (no printed-page concept available) |

`meta.json` (one per chapter, Gen 1–2 only):

| Field | Type | Notes |
|---|---|---|
| title | str | |
| printed_start | Optional[int] | |
| actual_start_idx, actual_end_idx | int | |
| page_count | int | `end - start + 1` |
| paragraph_mode | str | enum: `wrap` \| `oneline` |
| paragraph_chars | int | default 220, only meaningful in `wrap` mode |
| dehyphenated | bool | Gen 2 only; absent from Gen 1's meta.json entirely (Gen 1 never dehyphenates) |

### OutlineItem (`pdf_outline_to_csv.py`)

| Field | Type | Notes |
|---|---|---|
| title | str | normalized; may be a synthesized label, e.g. `"Chapter 3 — The Human Condition"`, `"[MAP] Map 2: ..."`, `"Zone 4 — ..."` |
| printed_start | int | 1-based page the heading/caption was found on |
| y | float | vertical position on page; used only for stable in-page ordering, dropped before CSV export |
| kind | str | enum: `toc`, `heading`, `caption`, `zone`, `other` — **not written to the output CSV** (see Gap 2) |

Output CSV columns (`data/work/outlines/<stem>_outline.csv`): `Sno, title,
printed_start[, printed_end if --include_end]`. `MASTER_outline.csv` (all
PDFs in one run) adds a leading `pdf` column.

### Row (`book_subcorpora_builder_v7.py`) — the hand-cleaned outline, read back in

| Field | Type | Notes |
|---|---|---|
| sno | int | from the `Sno` column |
| title | str | |
| start | int | from `printed_start` column |
| end | int | **not read from CSV** — always recomputed by `compute_page_ranges`, even if the CSV already has a `printed_end` column from `--include_end` |

### Section record (JSONL, `data/output/jsonl/<stem>_sections.jsonl`)

| Field | Type | Notes |
|---|---|---|
| pdf | str | `pdf_path.name` (includes `.pdf` extension, unlike the stem used for filenames elsewhere) |
| sno | int | |
| title | str | |
| printed_start, printed_end | int | |
| text | str | full extracted text for the page range, untruncated, no dehyphenation or paragraph splitting |

### Manifest record (CSV, `data/output/manifests/<stem>_manifest.csv`)

| Field | Type | Notes |
|---|---|---|
| pdf | str | |
| Sno | int | note the capitalization differs from the JSONL's lowercase `sno` — same value, inconsistent key casing across the two sibling output formats |
| title, printed_start, printed_end | | |
| txt_path | str | repository-relative for in-project outputs; absolute only for an explicitly external output root |
| chars | int | `len(text)` — a quality/size signal, no threshold enforced except the `--min_chars` drop filter (default `1`, effectively off) |

### Compound-phrase / topic-model outputs (`subcorpora_IR_template.ipynb`, notebook-only)

Not a stable schema — cell-by-cell `pandas` DataFrames written ad hoc to
`chapter_top_terms_words.csv`, `chapter_top_terms_compound.csv`,
`chapter_topics_nmf_compound.csv`, `chapter_clusters_kmeans_compound.csv`,
`chapter_summary_words.csv`, `chapter_summary_compound.csv`,
`paragraphs_raw.csv`, `paragraphs_enriched_compound.csv`,
`chapters_overview.csv`. Config constants live at the top of the notebook,
not in any shared file: `BASE_DIR`, `OUT_DIR`, `N_TOPICS=5`, `N_CLUSTERS=5`,
`NGRAM_RANGE=(1,3)`, `MIN_PARA_WORDS=8`.

## Enumerations, stated in full

- `paragraph_mode` (Gen 1–2 CLI and `meta.json`): `wrap`, `oneline`
- `OutlineItem.kind` (internal only, not persisted): `toc`, `heading`,
  `caption`, `zone`, `other`
- Caption label regex (`RE_CAPTION`/`RE_CAPTION_ALT` in
  `pdf_outline_to_csv.py`): `MAP`, `CHART`, `FIGURE`, `TABLE`, `PLATE`
  (case-insensitive; both `MAP 2` and `Map 2` spellings matched)
- Chapter-seed source, in fixed priority order (`book_subcorpora_builder_v6.py`
  `main()`): `chapters_from_csv` > `parse_toc_entries_from_pages` >
  `chapters_by_regex`

## Gaps

1. **Resolved: docstring/code path mismatch.** Live commands now use the
   shared `data/input/pdfs`, `data/work/outlines`, and `data/output` contract
   defined in `paths.py`; defaults are independent of the caller's CWD.
2. **`OutlineItem.kind` is computed but thrown away.** `pdf_outline_to_csv.py`
   classifies every candidate as `toc`/`heading`/`caption`/`zone`/`other`
   internally, then writes only `Sno, title, printed_start[, printed_end]`
   to CSV — the classification that would let a downstream consumer treat
   captions differently from chapter headings (e.g., exclude figure/table
   captions from a "chapters only" view) is not persisted anywhere.
3. **No record of whether an outline was actually reviewed.** The
   `_outline.csv` → `_outline_clean.csv` naming convention is the project's
   only human QA checkpoint, but it is a filename convention, not a tracked
   fact — a `_clean.csv` could be an untouched copy of the raw file and
   nothing would know.
4. **No config/topic layer.** Unlike the sibling `my_research_assistant`
   project's `ResearchProfile`, nothing here declares "what book collection
   is this" as data; genericity across the Gen 2 → Gen 3 book swap
   (Eurasia/geopolitics titles → Arendt/Berlin/Marcuse titles) worked only
   because no script ever hardcoded a title — a fragile kind of genericity
   that a single hardcoded title check would silently break.
5. **The notebook analysis layer (compound terms, NMF topics, KMeans
   clusters) was never adapted to Generation 3's output shape.** It still
   expects a Gen 1–2 `book*_subcorpora/chapter_XX/corpus.txt` tree; pointed
   at Generation 3's `chunks/sections/<stem>/NNN_<slug>.txt` +
   `chunks/jsonl/<stem>_sections.jsonl` layout, its `load_chapter_dirs()`
   would find nothing.
6. **Section records are produced but nothing consumes them.** No script or
   notebook in this project reads `chunks/jsonl/*_sections.jsonl` or
   `chunks/manifests/*_manifest.csv` back in — Generation 3's actual output
   format has no downstream inside this project (it presumably feeds an
   external tool, but that integration point is undocumented here).
7. **`debate_cast_tts.py` has no path from the corpus to the script it
   reads.** `debate_cast_script.txt` is hand-authored; nothing generates it
   from Chapter/Section text or from the notebook's topics — the mindmaps'
   "Q&A Bank"/"Policy Briefs" idea that would justify this connection is
   design-only.
8. **Dehyphenation was dropped, not superseded, in Generation 3.**
   `book_subcorpora_builder_v7.py` writes raw `pdfplumber` extraction
   straight to disk with no text cleanup step at all; Generation 2's
   `dehyphenate_text` has no equivalent here (see also
   `DIRECTION_OF_REFINEMENT.md` axis 3).
