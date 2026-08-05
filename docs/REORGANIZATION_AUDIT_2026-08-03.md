# Reorganization audit — 2026-08-03

## Scope

This pass addressed repository architecture and path portability. It did not
claim to repair the page-provenance algorithm or promote historical outputs to
citation-grade data.

## Findings addressed

- Generation 3 is now an installable package; Generations 1–2 are archived.
- Inputs, review CSVs, generated data, historical results, notebooks, and
  assets have explicit locations. `.idea/` and `.venv/` remain at the root for
  PyCharm/local-tool compatibility and are excluded by `.gitignore`.
- All live defaults now come from `src/bookcorpusbuilder/paths.py` rather than
  script location or the caller's working directory.
- The `otuput_dump` typo is now `archive/output_dump`; its contents were moved
  intact rather than rewritten.
- In-project manifest paths are repository-relative.
- The legacy analysis notebook targets the preserved Gen 2 corpus and writes
  new results into `data/output/analysis/`.
- Packaging metadata, dependency groups, CLI entry points, a README,
  architecture documentation, ignore rules, and basic tests were added.

## Validation

- Python compilation passed for the live package, tests, and archived code.
- Three architecture/unit tests passed.
- All three live commands parsed `--help` without optional dependencies.
- TOML and notebook JSON syntax were included in the final integrity sweep.

## Risks intentionally left open

- Generation 3 still conflates printed and physical PDF page coordinates.
- The outline detector can emit false positives and mixes coordinate origins.
- Writes are not run-atomic; incomplete runs can leave partial output.
- The legacy notebook still installs/downloads dependencies at run time and
  consumes the historical chapter format rather than current JSONL.
- There is no source-PDF rights/provenance ledger.

These remain tracked in `IMPROVEMENT_ROADMAP.md` and in the original technical
assessment under `docs/audits/`.
