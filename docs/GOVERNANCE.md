# BOOKCORPUSBUILDER Governance

```text
Status:        APPROVED
Applies from:   v1.0
Scope:          Entire repository
Adopted:        2026-08-04
Amended:        2026-08-05 (Section 7 — Workspace freeze policy; Workspace 2 frozen)
Amended:        2026-08-05 (Section 6 — Lifecycle sub-stages cross-referenced)
Amended:        2026-08-05 (Section 6 — Phase 2 complete, Phase 3 active)
Amended:        2026-08-05 (Section 1 — Page Alignment merged into Structure Builder
                as its "C. Page Mapping" tab; six-workspace architecture)
Amended:        2026-08-05 (Section 9 — Authorship policy: AI tools not credited
                as authors)
```

> **BOOKCORPUSBUILDER v1 is feature-complete in architecture. Future development
> shall optimize usability, robustness, performance, documentation, and operator
> efficiency rather than expand the conceptual scope of the application. Any
> proposal that enlarges the conceptual model shall be documented for a future
> v2 roadmap in `FUTURE_IDEAS_v2.md` and shall not be implemented in the v1
> production branch.**

This document is normative. It governs every contributor to this repository —
human or AI. When a proposed change conflicts with it, the change yields to
this document, not the other way around.

---

## 1. Architecture status: FROZEN

The following are stable contracts as of v1.0. They may be fixed, hardened, or
performance-tuned, but their shape does not change without a formal decision
that revises this document:

- The six-workspace architecture (Library, Structure Builder, Extraction,
  Corpus Browser, Run History, Settings). Page Alignment is no longer a
  standalone workspace — as of 2026-08-05 its verification UI was merged into
  Structure Builder's "C. Page Mapping" tab (alongside "A. Create Structure"
  and "B. Review Outline"); see the amendment log below for why.
- The outline schema (`OutlineEntry`, `BOOK_OUTLINE_CONTRACT_v1`).
- The page-mapping model (`PageMapping` / `MappingAnchor`, segmented offsets,
  the printed → physical → PDF-index coordinate chain). Unchanged by the
  Page Alignment UI merge above — `MappingService` and its persistence are
  untouched; only where the verification UI lives moved.
- The extraction pipeline (approved-mapping gate, run-scoped output).
- The corpus schema (section TXT / JSONL / manifest shape).
- Run history.
- The folder structure (`data/input`, `data/work`, `data/output`).
- The operator workflow (Import → Structure (build outline, then verify page
  mapping in the same workspace) → Extract → Browse).

## 2. Feature acceptance rule

A proposed feature shall be accepted into the v1 production branch only if
**all five** of the following hold:

1. It reduces operator effort.
2. It does not introduce a new conceptual model.
3. It does not require another workspace.
4. It preserves backward compatibility.
5. It can be explained in one paragraph in the Operator Manual.

If any one fails, the feature is **rejected or deferred to v2** — recorded in
`FUTURE_IDEAS_v2.md`, not implemented here.

## 3. Priority order for v1 work

```text
Priority A — Operator efficiency
  smoother layouts, keyboard shortcuts, batch operations, documentation,
  accessibility, stability

Priority B — Performance
  faster loading, caching, indexing, memory optimization

Priority C — Reliability
  regression tests, bug fixes, validation

Priority D — Packaging
  installer, executable, settings migration, updates
```

Work should generally be pulled from Priority A before B, B before C, and so
on, unless a lower-lettered priority is blocked on something only a
higher-lettered item can unblock (e.g., a packaging bug that blocks reliability
testing).

## 4. Explicitly out of scope for v1

The following enlarge the conceptual model and are therefore out of scope for
the v1 production branch, regardless of how individually compelling they are.
They belong only in `FUTURE_IDEAS_v2.md`:

- AI assistants (automatic heading/anchor suggestion, confidence-scored
  detection engines).
- Knowledge graphs.
- Topic modeling.
- Named-entity recognition.
- Semantic search expansion.
- Workflow redesign.
- New workspaces.

## 5. Change control

Every pull request, agent report, or Codex-style change report against this
repository should include a governance check:

```text
Governance Check

[ ] Reduces operator effort
[ ] New conceptual model introduced?
[ ] New workspace?
[ ] Backward compatible?
[ ] Operator Manual impact?

Decision: APPROVED / DEFERRED TO V2
```

An agent (AI or otherwise) proposing a change that fails the check should say
so explicitly and offer to record the idea in `FUTURE_IDEAS_v2.md` instead of
silently building it because it was asked for.

## 6. Lifecycle

```text
Phase 0 — Research                COMPLETE
Phase 1 — Architecture            COMPLETE
Phase 2 — Operationalization      COMPLETE
Phase 3 — Maintenance             ACTIVE
```

Phase 2 was scoped entirely by Sections 2 and 3 above: usability,
performance, reliability, and packaging — never new concepts. Across Phase
2, `UX_SPRINT_LOG.md`'s own sprint titles record three informal sub-stages,
in order:

```text
Workspace Maturation   — Sprints 1–12  (per-workspace UX programmes)
Product Refinement     — Sprints 13–16 (cross-cutting behaviour/consistency)
Release Preparation    — Sprints 17–18 (documentation, then release hardening)
```

These sub-stage names are not a new governance concept — they are the
existing sprint-brief titles, recorded here only so this document stays
synchronized with them.

**Phase 2 is complete.** The project owner formally accepted completion of
UX Sprint 18 (the independent Release Candidate audit), the RP-01 Release
Preparation task (version control initialization, version alignment,
release hygiene, and publication of the v1.0.0-rc1 baseline to
`https://github.com/ambijat/BOOKCORPUS_BUILDER`), and declared no automatic
Sprint 19 — the eighteen-sprint numbered programme is closed. Phase 3
(Maintenance) is therefore active.

**Operating model under Phase 3.** Future work is not a continuation of the
numbered sprint programme. It proceeds as normal version-controlled
maintenance and versioned evolution:

```text
inspect → define bounded change → branch → implement → test →
real-GUI verification where applicable → synchronize documentation →
review → merge
```

Any change that would enlarge the conceptual model (Section 4) is still
v2 work, not Phase 3 maintenance, regardless of this transition — Phase 3
governs *how* v1 evolves, not *whether* v1's scope can expand.

## 7. Workspace freeze policy

A workspace that has completed all planned UX sprints and has been
explicitly accepted is considered **frozen**. Subsequent changes require
either (a) a demonstrated regression, or (b) a new approved roadmap.
Routine enhancement requests must not reopen frozen workspaces.

The authoritative record of which workspace is frozen, and as of which
sprint, is the per-sprint acceptance entry in `UX_SPRINT_LOG.md` — check
there before proposing or making any change to a workspace listed below.

```text
Workspace                Status     Frozen as of
Structure Builder (WS2)  FROZEN     Sprint 8 (2026-08-05); regained an open
                                     exception on 2026-08-05 for the Page
                                     Alignment merge below, then re-frozen
Page Alignment           MERGED     Absorbed into Structure Builder (WS2) as
                                     its "C. Page Mapping" tab, 2026-08-05 —
                                     no longer tracked as its own workspace
```

This list is appended to as further workspaces are explicitly accepted as
complete; it is not retroactively inferred for a workspace just because its
most recent sprint went well — only an explicit "frozen" verdict from the
project owner adds an entry here.

Both Structure Builder and Page Alignment were frozen when the project owner
directed the 2026-08-05 merge described in the amendment log below — this
is the Section 7 "(b) a new approved roadmap" exception, exercised
explicitly, not a routine enhancement slipping past the freeze.

## 8. Authorship policy

No AI tool or agent (Claude or otherwise) shall be credited as an author or
co-author of any commit, document, or byline in this repository. This
applies to:

- Git commit trailers (e.g. `Co-Authored-By: Claude ...`).
- Document bylines, "Prepared by" lines, and signature lines (e.g. "— Claude").
- Any other author-of-record attribution in project sources.

The project owner is the author of record for all repository contents. An
AI tool may still be described in prose as having performed implementation
or analysis work (e.g. "an AI implementation agent"), but never named as
the credited author. This is a mandated policy, not a style preference —
it applies to all future commits and documents without exception.

## 9. Amending this document

This document can only be revised by an explicit, contemporaneous decision
from the project owner — not inferred from an enthusiastic feature request, a
compelling demo, or a persuasive pitch for what the software "could" do next.
A revision should update the `Adopted` date above and state what changed and
why.

**Amendment log:**
- 2026-08-05 — Merged Page Alignment into Structure Builder as a third tab
  ("C. Page Mapping", alongside "A. Create Structure" and "B. Review
  Outline"), reducing the workspace count from seven to six. Reason: the
  project owner's stated operating philosophy is that structural identity
  and page location belong in one review pass per book, not two separate
  workspaces reviewing the same outline entries from different angles —
  and every outline node already carries `printed_start` / `physical_start`
  / `pdf_page_index`, so a separate verification workspace duplicated
  review effort without adding a distinct data model. Explicitly directed
  by the project owner as the Section 7 "(b) new approved roadmap"
  exception to both workspaces' existing freezes (Structure Builder frozen
  Sprint 8, Page Alignment frozen Sprint 6), not inferred. Scope of the
  change: `AlignmentScreen` was relocated from `main_window.py` into
  `widgets/page_mapping.py` as `PageMappingPanel`, taking Structure
  Builder's shared PDF preview instead of owning a second one; navigation
  and lifecycle-target indices in `main_window.py` were renumbered
  accordingly. The mapping data model, `MappingService`, and the
  extraction pipeline's approved-mapping gate were **not** touched — this
  is a UI relocation, not a schema or algorithm change, so the page-mapping
  model entry in Section 1 remains frozen as before.
- 2026-08-05 — Added Section 7 (Workspace freeze policy) after the project
  owner accepted UX Sprint 6 and declared Workspace 3 (Page Alignment)
  frozen, to prevent routine enhancement requests from reopening a
  workspace whose planned UX sprints are complete.
- 2026-08-05 — Added Workspace 2 (Structure Builder) to the Section 7
  freeze table after the project owner accepted UX Sprint 8, completing
  the two-sprint Workspace 2 programme (Sprint 7: editing experience,
  Sprint 8: semantic classification).
- 2026-08-05 — Added a Section 6 cross-reference to the Workspace
  Maturation / Product Refinement / Release Preparation sub-stages
  already used in `UX_SPRINT_LOG.md`'s own sprint titles, during UX
  Sprint 17. Synchronized an existing, already-in-use concept; did not
  introduce a new governance rule or change any phase's status.
- 2026-08-05 — Marked Phase 2 (Operationalization) COMPLETE and Phase 3
  (Maintenance) ACTIVE in Section 6, with an operating-model statement
  for how work proceeds under Phase 3. Reason: the project owner formally
  accepted completion of UX Sprint 18 (the independent Release Candidate
  audit), RP-01 (Git initialization, version alignment to `1.0.0rc1`,
  release hygiene, and publication of the v1.0.0-rc1 baseline), and
  explicitly declared no automatic Sprint 19 — the eighteen-sprint
  programme is closed. This is the "explicit, contemporaneous decision
  from the project owner" this section requires, not an inferred or
  assumed transition.
- 2026-08-05 — Added Section 8 (Authorship policy), mandating that no AI
  tool or agent be credited as an author or co-author of any commit,
  document, or byline in this repository. Applied retroactively to the two
  "— Claude" signature lines and the "Prepared by: Claude" byline in
  `RETROSPECTIVE_ENGINEERING_REPORT.md`, replaced with a neutral role
  descriptor. Directed by the project owner.

See also: `FUTURE_IDEAS_v2.md` for the parking lot of deferred concepts, and
`IMPROVEMENT_ROADMAP.md` for the concrete, in-scope work items this governance
rule filters down to.
