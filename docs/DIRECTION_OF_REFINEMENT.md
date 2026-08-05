# Direction of Refinement — BOOKCORPUSBUILDER

Cross-references: `ONTOLOGICAL_BASIS.md` (entities/invariants this refinement
must preserve), `ATTRIBUTES.md` (gaps this queue is fed by).

## 1. Inheritance chain

| Generation | Artifact | Permanent contribution |
|---|---|---|
| Gen 1 — single-file chapter builder (`archive/legacy_code/book_subcorpora_builder_v5.py`, Aug 2025) | CSV→TOC→regex chapter-seed priority; printed/actual page-offset inference; `--crop-printed` window; `chapter_XX/{corpus.txt,meta.json}` output shape | The printed-vs-actual page distinction and its inference logic; the fixed CSV > TOC > regex precedence, unchanged in every later generation |
| Gen 2 — dehyphenation + regex fallback + notebook analysis (`archive/legacy_code/book_subcorpora_builder_v6.py`, Aug 2025) | `dehyphenate_text` with a real-word check and a preserved-compound set; `chapters_by_regex` fallback; legacy notebook analysis; TTS prototype; three Freeplane mind maps | Text-quality repair as a first-class concern; proof that a chapter corpus can support real topic modeling; an explicit vision that later generations still only partially implement |
| Gen 3 — decomposed, section-level pipeline (`src/bookcorpusbuilder/outline.py` + `src/bookcorpusbuilder/extract.py`, Jan 2026) | Layout-aware outline extraction; a human-reviewable outline artifact; section-level addressability with JSONL + manifest output | The idea that outline extraction and text extraction are separate concerns with a human checkpoint between them; the shift from "chapter to read" to "section to cite" |

## 2. Refinement axes

**Axis 1 — autonomous single-shot script → decomposed, reviewable pipeline.**
From: one invocation of `v5`/`v6` does detection and extraction together,
no intermediate artifact to inspect or correct (Gen 1–2). Toward: outline
extraction is its own persisted, human-reviewable CSV before any text is cut
(Gen 3). Constraint: a `_clean.csv` must remain hand-editable plain CSV, not
re-encoded into something a human can't easily fix.

**Axis 2 — chapter as the unit → section as the unit.**
From: one text blob per chapter meant to be read (Gen 1–2). Toward: many
smaller, individually titled, individually paged spans — headings, chapters,
and captions alike — meant to be cited or indexed (Gen 3). Constraint: every
section must still carry `printed_start`/`printed_end` provenance back to a
specific Book; losing that would defeat the entire reason for the shift.

**Axis 3 — text-quality repair → raw extraction.**
From: Gen 2 actively fixed line-wrap hyphenation before writing chapter text.
Toward: Gen 3 writes `pdfplumber` output completely unprocessed. This is
either a considered trade (sections are for machine indexing, where
downstream embedding/search tolerates a stray hyphen) or an unintentional
regression — nothing in Gen 3's code or docstring says which. This axis is
open, not decided; it should be resolved explicitly rather than left to
default (queue item 3).

**Axis 4 — ad hoc analysis notebook → no equivalent yet for the new output
shape.**
From: Gen 2's `subcorpora_IR_template.ipynb` proved compound-term/topic/
cluster extraction works on a chapter corpus. Toward: nothing yet reads
Gen 3's section-level JSONL the same way — the analysis layer simply stopped
tracking the pipeline's own evolution. Constraint: whatever replaces it
should read the manifest/JSONL contract already defined in `ATTRIBUTES.md`,
not reinvent a third output shape.

## 3. Governing discipline

Unlike `my_research_assistant`, this project has no written rule document —
its governing discipline has to be read out of consistent code behavior
rather than quoted from a README:

- **Printed page numbers are for humans; PDF indices are for code — never
  conflate them.** Every generation keeps both and provides an inference or
  override path between them. Any future change that starts indexing pages
  by PDF position alone would break every book with real front matter
  (title pages, dedications, TOC pages).
- **Prefer an explicit source of chapter/section boundaries (CSV) over an
  inferred one (TOC parse) over a guessed one (regex/bins), in that order,
  every time.** No generation has ever reversed this priority.
- **The Freeplane mind maps are the project's actual design document.**
  `Corpus_to_Deliverables.mm` and `Corpus_Applied_Model.mm` describe an
  Input → AI Extraction → Transformation → Output-Formats architecture that
  the code has only ever partially built; they should be treated as the
  standing target, not as disposable brainstorming, when deciding what a
  future stage ought to do.

## 4. Current position on the roadmap

- Chapter-level extraction (Gen 1–2 path): **done**, still present and
  runnable, but **superseded** in direction (not deleted) by the Gen 3
  section-level path.
- Outline auto-detection (Gen 3, `pdf_outline_to_csv.py`): **done**; its
  output classification (`kind`) is computed but not persisted — **not
  started** as a usable downstream signal (Attributes Gap 2).
- Human review checkpoint (`_clean.csv`): **proof-of-concept only** — the
  convention exists, but there is no tracked confirmation that review
  happened (Attributes Gap 3).
- Section-level extraction (Gen 3, `src/bookcorpusbuilder/extract.py`):
  **done and path-correct by default**. Shared defaults live in `paths.py`,
  and explicit input/output overrides remain available.
- Text-quality repair (dehyphenation) for the section-level path: **not
  started** — dropped from Gen 2, never re-added to Gen 3.
- Compound-term / topic / cluster analysis: **superseded-but-not-replaced**
  — proven once on the old chapter-corpus shape (Gen 2 notebook), not
  ported to the new section/JSONL shape.
- Debate-cast / teaching deliverables: **manual, disconnected prototype** —
  works, but takes a hand-written script, not corpus-derived content; the
  mindmaps' vision here is **not started**.
- Config/topic layer analogous to `ResearchProfile`: **not started** — not
  yet needed only because no script has ever hardcoded a book title.

## 5. Near-term queue

Ordered by dependency; each item traces to a gap in `ATTRIBUTES.md`.

1. **Completed (2026-08-03):** centralize paths and separate live inputs,
   reviewable work, generated outputs, and archives.
2. Persist `OutlineItem.kind` into the outline CSV (an extra column) so a
   downstream reader can separate chapter/part headings from figure/table/
   map captions without re-deriving the classification from the title
   string. Unblocks any future "chapters only" or "captions only" view.
3. Decide, and record the decision, on whether section-level extraction
   should regain a dehyphenation/text-cleanup pass — don't leave it as a
   silent side effect of the Gen 2→3 rewrite.
4. Port (or deliberately replace) the compound-term/NMF/KMeans notebook to
   read Gen 3's `data/output/jsonl/*_sections.jsonl` instead of the retired
   `chapter_XX/corpus.txt` layout, so the project's one working analysis
   layer isn't stranded on a superseded output format.
5. Give the outline-review checkpoint a machine-checkable trace (e.g. a
   `reviewed: true` marker or a diff check between raw and clean CSVs) so
   "was this actually reviewed" stops being an honor system.

## 6. The membership test

A future change belongs to this lineage only if every answer below is yes:

1. Does every chapter/section record keep printed-page and actual-PDF-index
   provenance separately, with an explicit or inferred offset between them?
2. When multiple boundary-detection sources are available, does CSV still
   win over parsed TOC, and parsed TOC still win over regex/heuristic
   guessing?
3. Does a human still get a plain, hand-editable CSV to review book
   structure before any page text is cut and written out?
4. Does the change keep working on an arbitrary book collection without
   requiring a title, topic, or filename to be hardcoded anywhere in the
   script?
