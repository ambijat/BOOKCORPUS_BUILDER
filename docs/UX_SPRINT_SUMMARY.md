# UX Sprint Summary — Sprints 1–16

This is a **maintainer-facing index**, not an operator document. It summarizes
what each accepted UX sprint set out to do, which workspace(s) it touched, and
what the project owner accepted as the outcome — in one line each, so a new
maintainer can find the sprint that explains a given piece of behavior without
reading the full, detailed record.

**Full detail for every sprint** (audit findings, exact files changed, test
results, real-GUI verification steps, and risks) lives in
[`UX_SPRINT_LOG.md`](UX_SPRINT_LOG.md) — this document only indexes it. When in
doubt about *why* something behaves a certain way, or whether a workspace is
frozen, `UX_SPRINT_LOG.md` and [`GOVERNANCE.md`](GOVERNANCE.md) are the
authoritative sources, not this summary.

## Stage 1 — Workspace Maturation (Sprints 1–12)

Each sprint in this stage improved exactly one workspace's user experience —
no cross-cutting behavior yet.

| Sprint | Workspace | Objective | Outcome |
|---|---|---|---|
| 1 | 5 · Corpus Browser | Initial UX pass: search, filters, results, metadata | Accepted |
| 2 | 6 · Run History | Table of past runs, output access | Accepted |
| 3 | 4 · Extract | Preflight, dry run, progress, structured logs | Accepted |
| 4 | 3 · Page Alignment | Anchor workflow (add/remove verification anchors) | Accepted |
| 5 | 3 · Page Alignment | Conflict resolution and diagnostics | Accepted |
| 6 | 3 · Page Alignment | Verification dashboard and completion experience | Accepted — **Workspace 3 declared FROZEN** (`GOVERNANCE.md` §7) |
| 7 | 2 · Structure Builder | Outline editing experience | Accepted |
| 8 | 2 · Structure Builder | Semantic classification of outline rows | Accepted — **Workspace 2 declared FROZEN** (`GOVERNANCE.md` §7) |
| 9 | 1 · Library | Project cockpit: status columns, book summary panel | Accepted |
| 10 | 5 · Corpus Browser | Research reading experience (three-pane preview) | Accepted |
| 11 | 5 · Corpus Browser | Research retrieval (filters, run scoping) | Accepted |
| 12 | 7 · Settings | Configuration experience, path validation, live status | Accepted |

## Stage 2 — Product Refinement (Sprints 13–16)

Each sprint in this stage was **cross-cutting** — one behavior or convention
applied consistently across all seven workspaces, rather than one workspace
improved in isolation.

| Sprint | Scope | Objective | Outcome |
|---|---|---|---|
| 13 | All workspaces | Shared background-task lifecycle (`run_task()`): one task indicator, one "Last action" label, failed tasks reset the calling workspace's own UI state instead of leaving it stuck | Accepted |
| 14 | All workspaces | Operator navigation & keyboard workflow: safe-by-default destructive confirmations, focus recovery after Add/Delete/Move, Enter-to-submit, buddy-label accessibility gap closed | Accepted |
| 15 | All workspaces | Error reporting & recovery: one shared `format_operator_error()` Reason/What-you-can-do dialog structure, technical details always preserved behind "Show Details," never discarded | Accepted |
| 16 | All workspaces | Product consistency audit: Title Case buttons/headings/table headers/dialog titles, one icon per concept (no duplicate blocking-state icons), one wording per action across workspaces | Accepted |

**Constant across all four Stage 2 sprints:** Page Alignment (WS3) and
Structure Builder (WS2) are formally frozen, yet each received small,
explicitly-flagged touches in this stage — every one was interaction
plumbing, wording, or a status icon, never layout or business logic. Where a
consistency fix would have required touching frozen, tested prose (e.g. Page
Alignment's own button labels in Sprint 16), it was deliberately left
unchanged and documented instead of forced through.

## Stage 3 — Release Preparation (Sprints 17–18)

| Sprint | Scope | Objective | Outcome |
|---|---|---|---|
| 17 | Documentation | Bring every documentation artifact (Operator Manual, GUI notes, governance, screenshots) up to date with Sprints 1–16, and produce the maintainer/release-facing documents this file is part of | Accepted |
| 18 | Independent release audit | Not a development sprint — an evidence-based audit of whether v1.0 is ready to ship: code audit, regression verification, workspace walkthrough, documentation/governance consistency, packaging, and a final GO/NO-GO recommendation | See `RELEASE_CANDIDATE_REPORT.md` |

## How to use this file

- **Looking for *why* a button says what it says, or why a dialog looks the
  way it does?** Find the relevant sprint number above, then read that
  sprint's full entry in `UX_SPRINT_LOG.md`.
- **Wondering if a workspace can be changed freely?** Check
  `GOVERNANCE.md` §7's freeze table first — Structure Builder (WS2) and Page
  Alignment (WS3) are frozen; the other five are mature but not formally
  frozen.
- **This file does not replace `UX_SPRINT_LOG.md`.** It is deliberately terse
  — one line of outcome per sprint — and omits audit findings, discovered
  bugs, deferred items, and test counts, all of which are load-bearing detail
  kept only in the full log.
