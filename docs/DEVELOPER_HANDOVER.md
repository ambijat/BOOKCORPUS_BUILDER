# Developer Handover — BOOKCORPUSBUILDER

This document orients a new maintainer or contributor who has not been part
of this project's prior development sessions. It is deliberately short and
points to the authoritative source for each topic rather than duplicating it
— if this document and the file it points to ever disagree, the pointed-to
file wins.

## Start here, in order

1. **`README.md`** — setup, install, and the CLI pipeline.
2. **`docs/ARCHITECTURE.md`** — directory layout, dependency direction, data
   lifecycle, GUI safety boundary.
3. **`docs/GOVERNANCE.md`** — the rules every change to this repository must
   pass, including the workspace-freeze table.
4. **`docs/GUI.md`** — what the desktop application actually does, workspace
   by workspace, including the Sprint 13–16 cross-cutting behavior.
5. **`docs/UX_SPRINT_SUMMARY.md`** — one line per sprint, so you can find
   which sprint explains a piece of behavior without reading the full log.
6. **`docs/OPERATOR_MANUAL.md`** — what an operator sees and does, chapter by
   chapter; useful as a spec of intended behavior when you're not sure what a
   button is *supposed* to do.

## Architecture, in one paragraph

The installable package (`src/bookcorpusbuilder/`) separates a Qt-free
service/pipeline layer (`outline.py`, `extract.py`, `outline_contract*.py`,
`paths.py`) from the PySide6 GUI (`gui/`), which imports those services
directly rather than shelling out to the CLI. The GUI itself separates domain
models (`gui/models/`), a service layer (`gui/services/`) that never imports
Qt, and widgets/workers (`gui/widgets/`, `gui/workers/`) that do. Long-running
work (detection, extraction, Ollama generation) always runs through one
shared path, `MainWindow.run_task()`, which owns the QThread lifecycle so no
individual workspace has to. Full detail: `docs/ARCHITECTURE.md`.

## Frozen workspaces — read before touching Workspace 2 or 3

Per `docs/GOVERNANCE.md` §7, **Structure Builder (Workspace 2)** and **Page
Alignment (Workspace 3)** are frozen — each completed its own planned UX
programme and received an explicit "frozen" verdict from the project owner
(Sprint 8 and Sprint 6 respectively). Frozen does not mean untouchable: four
cross-cutting sprints since (13–16) each made small, interaction-only changes
to both (a safer confirmation default, focus recovery, a shared error-dialog
structure, wording/casing consistency) — but every one of those changes was
explicitly flagged in `UX_SPRINT_LOG.md` at the time, and none touched
layout, validation rules, or business logic. If you need to change either
workspace's *behavior* (not just wording), that requires a new approved
roadmap, not a routine PR — see `GOVERNANCE.md` §7 before starting.

The other five workspaces (Library, Extract, Corpus Browser, Run History,
Settings) are mature and stable but **not** formally frozen; they can be
enhanced with more latitude, still subject to the 5-point feature-acceptance
rule in `GOVERNANCE.md` §2.

## Extension points

- **New outline source in Structure Builder**: add a button to the "Choose a
  structure source" row and a method that produces `OutlineCandidate` rows
  into the existing candidate table — every existing source (paste, PDF
  detection, CSV, JSON, Ollama, manual) converges on that one model, so a new
  source only needs to produce it, not its own review UI.
- **New background operation anywhere**: call `window.run_task(function,
  callback, ..., on_failure=...)` rather than spinning up a `QThread`
  directly — this is what gives a new operation the shared task indicator,
  "Last action" label, and consistent failure dialog for free.
- **New operator-facing error**: call `self.window.show_error(title,
  format_operator_error(reason, next_steps), details)` (see
  `gui/widgets/dialogs.py`) rather than composing a message string inline —
  this is what Sprint 15 centralized specifically so every error reads the
  same way.
- **New table**: use `configure_table()` (`gui/widgets/table_usability.py`)
  for frozen columns, persisted column widths, and Best Fit Columns, rather
  than configuring a `QTableWidget` from scratch.

## Coding philosophy this codebase has converged on

- **Centralize, then reuse — don't re-derive per workspace.** `run_task()`,
  `format_operator_error()`, `confirm_destructive()`, and `configure_table()`
  all exist because the same problem kept recurring per-workspace; each was
  extracted only after a second or third occurrence made the duplication
  concrete, not speculatively.
- **Preserve technical detail; never show it by default.** Every error
  dialog keeps the real exception and traceback available behind "Show
  Details" — operator-facing text is always plain language, developer detail
  is always one click away, never discarded.
- **A blocking state names the exact blocker and the exact fix.** Page
  Alignment and Structure Builder's validation panels never say "invalid" —
  they name the section, the printed page, and the specific corrective
  action. Follow this pattern for any new validation rule.
- **Real GUI verification, not just widget-state assertions.** Every UX
  sprint's report includes a real-GUI verification pass (offscreen Qt
  platform, an isolated scratch `BOOKCORPUSBUILDER_CONFIG` project, real
  fixture PDFs) in addition to the pytest suite — this is how the Sprint 17
  documentation pass caught a real layout-overflow issue (see
  `Release_Notes_v1.0_DRAFT.md`, "Known limitations") that no existing test
  assertion had surfaced.
- **Restraint in frozen workspaces, restraint everywhere else too.** The
  Engineering Guidance repeated across Sprints 14–17 — "do not improve a
  workspace that is already consistent," "if an inconsistency can't be
  resolved without risk, document it rather than force it" — is not
  sprint-specific advice; it is how this codebase expects contributors to
  behave by default.

## Governance principles (see `GOVERNANCE.md` for the normative text)

- v1 is architecturally frozen: usability, performance, reliability, and
  packaging work is in scope; enlarging the conceptual model (new
  workspaces, AI assistants, knowledge graphs, semantic search expansion) is
  not, and belongs in `FUTURE_IDEAS_v2.md` instead.
- A proposed feature is accepted only if it reduces operator effort,
  introduces no new conceptual model, needs no new workspace, stays backward
  compatible, and can be explained in one paragraph of the Operator Manual.
  Any agent (human or AI) proposing a change that fails this test should say
  so explicitly rather than building it anyway.
- The authoritative record of what's frozen and why is the per-sprint
  acceptance entry in `UX_SPRINT_LOG.md` — not inferred from a sprint having
  gone well.

## Known open items for the next maintainer

See `Release_Notes_v1.0_DRAFT.md`'s "Known limitations" and "What Sprint 18
still needs to do" sections — both are written for exactly this audience.
