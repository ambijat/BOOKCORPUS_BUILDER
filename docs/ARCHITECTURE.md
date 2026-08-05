# Project architecture

```text
BOOKCORPUSBUILDER/
├── src/bookcorpusbuilder/       installable pipeline and shared paths
│   ├── paths.py                 canonical repository/data locations
│   ├── outline.py               stage 1: PDF → reviewable outline CSV
│   ├── outline_contract.py      book_outline_contract v1.0.0 Pydantic models
│   ├── outline_contract_repository.py  versioned per-book contract storage
│   ├── outline_hashing.py       SHA-256 hashing helpers for contract/approval records
│   ├── outline_validation.py    shared outline validation rules
│   ├── ollama_outline_generator.py  optional local-Ollama candidate generation
│   ├── extract.py               stage 2: approved outline → corpus
│   ├── tts.py                   optional narration utility
│   └── gui/                     PySide6 UI, domain models, services, workers
├── schemas/                     generated JSON Schema (book_outline_contract_v1.schema.json)
├── scripts/                     one-off maintenance/utility scripts
├── tests/                       pytest suite (unit + real-widget GUI tests)
├── data/
│   ├── input/pdfs/              authoritative source PDFs (read-only input)
│   ├── work/outlines/           machine drafts and human-approved outlines
│   └── output/                  regenerated sections, JSONL, manifests, analysis
├── notebooks/                   experiments and downstream analysis
├── assets/                      diagrams and narration source text
├── docs/                        current design, roadmap, and audits
├── .idea/                       retained local PyCharm project configuration
├── .venv/                       retained local Python environment
└── archive/
    ├── legacy_code/             superseded Generation 1/2 builders
    └── output_dump/             historical results (formerly `otuput_dump`)
```

## Dependency direction

`paths.py` owns all default locations. Command modules may depend on it; it does
not depend on pipeline code. Inputs are never created automatically. Work and
output directories may be created by commands. Archived code and outputs are
not imported by the live package. Root-level `.idea/` and `.venv/` are local
tooling and remain excluded by `.gitignore`.

## Data lifecycle

```text
data/input/pdfs
  → bookcorpus-outline
  → data/work/outlines/*_outline.csv
  → human review (*_outline_clean.csv)
  → bookcorpus-extract
  → data/output/{sections,jsonl,manifests}
```

Paths written to manifests are repository-relative when outputs live inside the
project, avoiding the former machine-specific `/media/...` values.

## GUI safety boundary

The GUI imports live package functions and services directly; it does not run
the CLI through subprocesses. Qt widgets depend on a Qt-free service layer.
Long outline, scan, and extraction operations run in `QThread` workers.

Enhanced outline CSVs preserve `printed_start`, `physical_start`, and
`pdf_page_index`. Approval and page mapping are separate hashable sidecars.
GUI extraction writes to a run-scoped temporary directory, validates completion,
then atomically promotes it to `data/output/runs/<run_id>/`. Immutable run JSON
records live under `data/output/run_history/`.
