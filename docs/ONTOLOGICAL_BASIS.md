# Ontological Basis — BOOKCORPUSBUILDER

Extracted per `ONTOLOGIES/ONTOLOGY_EXTRACTION_GUIDE.md`. Cross-references:
`ATTRIBUTES.md`, `DIRECTION_OF_REFINEMENT.md`.

## 0. What this project is, in one line

A PDF-to-subcorpus tool: it turns a book-length PDF into addressable,
citable text units (chapters, then sections) with page provenance, so the
result can be fed into text-analysis or retrieval tooling downstream — and,
in its own aspirational design documents, eventually into summaries,
glossaries, knowledge graphs, and teaching material.

## 1. Reading of Existing Versions

Three generations were read, in chronological order (see
`DIRECTION_OF_REFINEMENT.md` for exact dates/evidence).

**Generation 1 — `archive/legacy_code/book_subcorpora_builder_v5.py` (Aug 2025, "fresh
single file").** A single script, single responsibility: given a PDF and
(preferably) a `title,printed_start` CSV, find chapter boundaries — via CSV
seeds, else TOC-page parsing (dotted leaders / tail numbers / split-line
formats), else nothing — infer the printed-to-actual page offset, crop to a
`--crop-printed` window, and write one `chapter_XX/corpus.txt` +
`chapter_XX/meta.json` per chapter. The central object is the **chapter**,
identified only by its page range; there is no per-paragraph or per-section
addressability yet.

**Generation 2 — `archive/legacy_code/book_subcorpora_builder_v6.py` (Aug 2025, same week; the
version captured in the parent `BOOKCORPUSBUILDER.zip` backup).** Adds a
regex-based chapter-detection fallback (`chapters_by_regex`, keyed on
`CHAPTER_START_RE` / equal-bin splitting) for PDFs with neither CSV nor
parseable TOC, and — its main addition — automatic **dehyphenation**:
line-wrapped words (`word-\ncontinuation`) are rejoined using a real-word
check (`wordfreq` if installed, else a length heuristic) while a
hand-maintained set of legitimate compounds (`policy-making`, `long-term`,
…) is preserved. Paragraph chunking gains a `wrap`/`oneline` mode. This
generation is also where a downstream analysis layer appears, but only as a
**notebook**, never promoted to a `.py` stage: `subcorpora_IR_template.ipynb`
reads a `book*_subcorpora/chapter_XX/corpus.txt` tree and produces TF-IDF,
POS-pattern **compound-phrase** extraction (`"balance of power"`,
`"regional security complex"`), NMF topics, and KMeans clusters per chapter,
landing in a separate `*_subcorpora_outputs/` folder of CSVs. Two Freeplane
mind maps from this same week (`corpusknowledge1.mm`, `Corpus_Applied_Model.mm`,
`Corpus_to_Deliverables.mm`) record the *intended* full architecture —
Input → AI Extraction (entities, themes, timelines, relationships) →
Transformation (textual/tabular/visual/analytical/digital) → Output formats
(files/web/teaching) — of which the code at this point implements only the
first two stages (chapter extraction, ad hoc topic modeling). A standalone
`debate_cast_tts.py` also appears, turning a **hand-written** dialogue script
into a WAV/MP3 via `pyttsx3`/`espeak-ng`/`ffmpeg` — a real instance of the
mindmap's "Teaching/Digital" branch, but not derived from the corpus at all.

**Generation 3 — `src/bookcorpusbuilder/outline.py` + `src/bookcorpusbuilder/extract.py`
(current, dated Jan 2026).** A deliberate architectural split. Chapter/TOC
detection is pulled out into its own layout-aware tool
(`pdf_outline_to_csv.py`): it clusters `pdfplumber` words into lines, scores
each line by font-size percentile and boldness/centering, matches
`PART/CHAPTER/INTRODUCTION/ACKNOWLEDGMENTS` and `MAP/CHART/FIGURE/TABLE/PLATE`
keyword patterns, merges a caption marker with its following title line, and
writes one `<pdf>_outline.csv` per PDF plus a `MASTER_outline.csv` across a
whole folder. The granularity is finer than "chapter": captions and
part-headings become their own rows, named `[MAP] Map 3: …` etc. This raw
CSV is meant to be hand-reviewed into a `*_outline_clean.csv` — the filename
convention itself documents a human QA checkpoint that generation 1–2 did not
have. `extract.py` ("Stage 2") consumes only the clean CSV
(no TOC-parsing, no regex fallback, no dehyphenation of its own): it computes
each row's `printed_end` as the next distinct `printed_start` minus one,
extracts that page range with `pdfplumber`, and writes a per-**section** (not
per-chapter) `.txt`, one JSONL record per section, and a manifest CSV — a
shape clearly meant for indexing/retrieval rather than for reading a chapter
end to end. The corpus itself changed too: `local_books_v1/book1.pdf` /
`book2.pdf` / `book3.pdf` (anonymous stand-ins, matched to the Eurasia/
geopolitics mindmap examples) are archived; `data/input/pdfs/` now holds four
named political-theory PDFs (Arendt, Berlin, Marcuse). Neither the topic nor
the code changed to accommodate this — genuine topic-agnosticism by default,
not by any config layer (contrast `ATTRIBUTES.md` Gap 4).

**The central-object shift, named explicitly:** Generation 1–2 treated the
**chapter** as the unit worth producing — one text blob per chapter, read
start to end. Generation 3 shifts the unit down to the **section** (a
titled sub-range that may be a heading, a caption, or a chapter), each with
its own manifest row and JSONL record — the unit is no longer "a chapter to
read" but "a citable, indexable span of pages."

## 2. Entities

### Structural entities — where things live

**Book (PDF Source).** A single book-length PDF to be mined for text.
- *Current code expression:* a file under `data/input/pdfs/` (Gen 3),
  addressed everywhere by its filename stem
  (`pdf_path.stem`).
- *Future role:* unchanged; every other entity below exists to describe a
  span of one Book.

**Outline.** The ordered list of a Book's chapters/sections/captions with
their starting printed page — the map used to cut the PDF into pieces.
- *Current code expression:* Gen 1–2 built this in memory only
  (`ChapterDef` list), never persisted independent of a run. Gen 3 persists
  it as a first-class artifact: `data/work/outlines/<stem>_outline.csv`
  (machine-generated, `OutlineItem`-derived) and, after human review,
  `data/work/outlines/<stem>_outline_clean.csv` (`Row`-shaped: `Sno, title,
  printed_start`).
- *Future role:* the hand-cleaning step is the project's only human-in-the-
  loop checkpoint; nothing yet tracks whether a given `_clean.csv` has
  actually been reviewed (see Gap 3).

**Subcorpus / Chunk Store.** The output tree of extracted text for one Book,
organized by chapter (Gen 1–2) or by section with a JSONL ledger and
manifest (Gen 3).
- *Current code expression:* Gen 1–2: `<outdir>/chapter_XX/{corpus.txt,
  meta.json}`. Gen 3: `data/output/sections/<stem>/NNN_<slug>.txt` +
  `data/output/jsonl/<stem>_sections.jsonl` + `data/output/manifests/<stem>_manifest.csv`.
- *Future role:* the thing a downstream retrieval/embedding tool (this
  project's own `subcorpora_IR_template.ipynb`, or an external tool such as
  the sibling `my_research_assistant` pipeline) would consume.

### Provenance entities — where things came from

**Chapter (Gen 1–2 unit).** A page-range slice of a Book with a title and a
printed-page start/end, plus derived text.
- *Current code expression:* `ChapterDef` dataclass — `title,
  start_page_idx, end_page_idx, printed_start` — paired with `meta.json`'s
  `{title, printed_start, actual_start_idx, actual_end_idx, page_count,
  paragraph_mode, paragraph_chars, dehyphenated}`.
- *Future role:* superseded in kind by Section (Gen 3), but the concept
  (title + printed-page span) survives inside Section's `Row`.

**Section (Gen 3 unit).** A finer-grained, page-ranged, titled span — a
heading, a chapter, or a captioned figure/table/map — with citable
provenance.
- *Current code expression:* `Row` dataclass in `book_subcorpora_builder_v7.py`
  — `sno, title, start, end` — and its JSONL/manifest projection: `{pdf, sno,
  title, printed_start, printed_end, text}` / `{pdf, Sno, title,
  printed_start, printed_end, txt_path, chars}`.
- *Future role:* the intended atomic citation unit; nothing downstream
  (yet) consumes it — see Gap 5.

**Compound Term / Topic / Cluster (notebook-only entities).** A multi-word
noun phrase (`"balance of power"`), an NMF topic, or a KMeans cluster,
computed per chapter from the Gen 1–2 chapter corpus.
- *Current code expression:* only inside `subcorpora_IR_template.ipynb` —
  `df_paras`, `phrase_counts`, `df_terms_words` /
  `df_terms_compound`, NMF/KMeans outputs written to
  `chapter_topics_nmf_compound.csv`, `chapter_clusters_kmeans_compound.csv`,
  `chapter_top_terms_*.csv`, `chapter_summary_*.csv`.
- *Future role:* the mindmaps' "Analytical Outputs" (thematic clusters,
  policy notes) depend on this layer, but it was never promoted to a
  reusable `.py` stage and never adapted to read Gen 3's Section output
  instead of Gen 1–2's chapter directories — see Gap 2.

### Process entities — how things move

**Outline Extraction (process).** Turning a raw PDF into an Outline via
layout heuristics.
- *Current code expression:* `pdf_outline_to_csv.py::extract_outline_from_pdf`
  — TOC-page parsing first (`parse_toc_pages`), then whole-document
  layout-scoring (`guess_heading_candidates`: 90th-percentile font size,
  bold ratio, centeredness) merged with keyword regex
  (`PART/CHAPTER/INTRODUCTION/ACKNOWLEDGMENTS/MAP/CHART/FIGURE/TABLE/PLATE/
  Zone`), then caption-title merging, then dedupe-by-earliest-occurrence.
- *Future role:* unchanged; this is the project's most sophisticated single
  function and the thing most worth preserving across future rewrites.

**Dehyphenation (process, Gen 2 only).** Rejoining a word broken across a
line wrap without also joining legitimate hyphenated compounds.
- *Current code expression:* `book_subcorpora_builder_v6.py::dehyphenate_text`,
  gated on `is_probable_word` (via `wordfreq.zipf_frequency` if installed,
  else a crude regex+length heuristic) and a hardcoded
  `DEFAULT_KEEP_HYPHENS` set.
- *Future role:* dropped, not replaced, in Gen 3 — `book_subcorpora_builder_v7.py`
  does no text cleanup at all on its extracted section text. Whether this
  was deliberate (Gen 3's sections are meant for machine indexing, where a
  stray hyphen matters less) or an accidental regression is unresolved — see
  `DIRECTION_OF_REFINEMENT.md` axis 3.

**Text Extraction (process).** Pulling raw text out of a PDF page range.
- *Current code expression:* Gen 1–2 use PyMuPDF (`fitz`,
  `doc.load_page(i).get_text("text")`); Gen 3 uses `pdfplumber`
  (`pdf.pages[p].extract_text()`) instead — a library switch with no stated
  reason found in any comment or doc.
- *Future role:* unchanged in purpose; the library choice itself is a
  latent inconsistency (Gap 1).

**Debate Cast Synthesis (process, disconnected).** Turning a text script
into spoken audio.
- *Current code expression:* `debate_cast_tts.py`, reading a hand-authored
  `debate_cast_script.txt`, not any corpus/section output.
- *Future role:* the mindmaps imagine this fed by the corpus itself
  (Q&A banks, policy briefs); today it is entirely manual input — see Gap 6.

## 3. Relationship spine

```text
Book                produces   Outline               (via Outline Extraction)
Outline (raw)       ->         Outline (clean)        (human review, manual)
Outline (clean)     produces   Section                (via Text Extraction, Gen 3)
Book                produces   Chapter                (via Text Extraction, Gen 1-2, superseded)
Chapter             cites      Book                   (page range)
Section             cites      Book                   (page range)
Chapter             produces   Compound Term / Topic / Cluster   (notebook only)
Debate Cast          ...       (no edge to any of the above — manual input only)
```

Collapsed to one pipeline, current generation:

```text
Book (PDF) -> Outline Extraction -> Outline (raw CSV)
  -> [human review] -> Outline (clean CSV)
  -> Text Extraction -> Section (txt + JSONL + manifest)
```

Collapsed, Generation 1–2 (still the only path that reaches topic
modeling, via the disconnected notebook):

```text
Book (PDF) -> Chapter Detection (CSV/TOC/regex) -> Dehyphenation
  -> Chapter (corpus.txt + meta.json)
  -> [subcorpora_IR_template.ipynb, manual] -> Compound Terms / Topics / Clusters
```

## 4. Invariants

1. **Printed page ≠ actual PDF index.** Every stage that deals in page
   numbers keeps `printed_start`/`printed_end` (what a human reading the
   book sees) separate from `start_page_idx`/`end_page_idx` (0-based
   position in the PDF file), with an explicit, inferable or overridable
   offset (`printed_to_actual_index`, `infer_printed_offset`,
   `--printed-offset`). Collapsing the two would silently misalign every
   chapter/section boundary in any front-matter-heavy book.
2. **A range's end is the next distinct start, minus one.** Both
   generations compute section/chapter end pages the same way
   (`add_page_ranges` in Gen 1's TOC parser; `compute_page_ranges` in Gen 3):
   look forward for the next *different* start value, not merely the next
   row, so that multiple hierarchy levels sharing one `printed_start`
   (e.g., a Part heading and its first Chapter) correctly extract the same
   opening range rather than a zero-length one.
3. **Preserve known hyphenated compounds; never invent a word.**
   `DEFAULT_KEEP_HYPHENS` is checked before attempting to join a
   line-wrapped hyphen, and joining only proceeds when the joined form
   passes `is_probable_word`. (Gen 2 only — see Gap/axis on whether this
   should return in Gen 3.)
4. **A CSV of chapter seeds beats parsed TOC beats regex guessing**, in that
   fixed order, at every generation (`if args.chapters_csv: … else: toc …
   else: regex …`). Precision is explicitly prioritized over autonomy.

## 5. State machine

No explicit state field exists anywhere; state is, as in the sibling
`my_research_assistant` project, implicit in which output files/folders
exist for a given Book (identified by filename stem):

```
(PDF only, in data/input/pdfs/)
  -> outline extracted (data/work/outlines/<stem>_outline.csv)
  -> outline reviewed  (data/work/outlines/<stem>_outline_clean.csv, human step)
  -> sections extracted (data/output/sections/<stem>/, data/output/jsonl/<stem>_sections.jsonl,
                          data/output/manifests/<stem>_manifest.csv)
```
or, via the still-available Gen 1–2 path:
```
(PDF only) -> chapters extracted (<outdir>/chapter_XX/) -> [manual: run notebook]
  -> topic-modeled (<outdir>_outputs/*.csv)
```
Nothing marks which path (Gen 3 section-based, or Gen 1–2 chapter-based) was
used for a given Book, and nothing prevents both from being run against the
same Book into different output trees with no cross-reference.
