# External audit package

This repository can be repacked as a data-minimized ZIP for review by an
external agent. The package is intended for architecture, correctness,
security, reproducibility, and maintainability auditing—not for reproducing
the PDF extraction results against the original books.

## Included

- Live package code and tests
- Packaging and command configuration
- Current architecture, model, roadmap, and reorganization documentation
- Superseded Generation 1/2 Python code for regression/history comparison
- Legacy notebooks with saved execution outputs removed
- Diagrams and the synthetic debate-script fixture
- Empty input/work/output directory structure

## Deliberately excluded

- `.venv/` and `.idea/`
- Source PDFs under `data/input/pdfs/`
- Generated/reviewed data under `data/work/` and `data/output/`
- Historical corpora, PDFs, audio, and analysis under `archive/output_dump/`
- Pre-reorganization audit snapshots containing obsolete machine-local paths
- Python caches and build/test caches

The exclusions minimize copyrighted content, derived corpus data, local
machine metadata, and unnecessary upload size. File hashes and a full archive
listing accompany the ZIP in `dist/`.
