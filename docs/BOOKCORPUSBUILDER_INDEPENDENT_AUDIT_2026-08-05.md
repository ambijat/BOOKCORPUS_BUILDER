# BOOKCORPUSBUILDER — Independent Release-Candidate Audit

**Audit date:** 2026-08-05  
**Audited package:** `BOOKCORPUSBUILDER_v1.0.0-rc1_AUDIT_2026-08-05_130753.zip`  
**Auditor:** Independent review performed from the submitted archive, not from sprint reports alone.

## 1. Executive verdict

**Verdict: CONDITIONAL GO for private/internal RC use; NO-GO for a public or externally distributed v1.0.0 release until release hygiene is corrected.**

The application architecture, service boundaries, safety model, operator documentation, and test design are materially stronger than a typical pre-1.0 desktop research tool. The submitted package supports the view that the product is functionally mature. However, the release package itself contains several contradictions and leaks that should be corrected before it is treated as a clean release artifact:

1. The package metadata still declares application version **0.2.1**, while the archive and reports call it **v1.0.0-rc1**.
2. The audit archive includes `.bookcorpusbuilder.local.json` and `.idea/workspace.xml`, exposing machine-specific absolute paths despite both being ignored by `.gitignore` and despite the package being described as audit-safe.
3. `README.md` contains two broken links to DOCX files removed from the archive.
4. No license exists.
5. No Git repository/history exists.
6. The full claimed 213-test GUI result could not be independently reproduced in this audit environment because PySide6 was unavailable and the local package index could not satisfy build dependencies. The non-GUI subset independently passed: **68 passed, 9 skipped**. Source compilation passed.

These are release-engineering defects, not evidence that the core corpus workflow is unsound.

## 2. Package integrity

- External SHA-256 matched the supplied checksum: `61f95ca030a5058f2772513358de41c6dd3893a59912114660982eecb31d7997`.
- ZIP extraction succeeded.
- Internal `AUDIT_FILE_HASHES.sha256` verification succeeded for submitted files.
- Package size after extraction: approximately 9.9 MB and 193 files.

## 3. Architecture assessment

### Strengths

- Clear installable `src/` layout and console entry points.
- Qt-free service layer separated from PySide6 widgets.
- Domain models, services, widgets, and workers are separated coherently.
- Page mapping is modeled explicitly rather than silently assuming printed page equals PDF page.
- Outline approval and mapping approval are distinct artifacts.
- Extraction uses temporary run directories and atomic promotion.
- Source hashes and run-scoped outputs provide strong provenance.
- Optional Ollama integration is isolated and schema-constrained rather than embedded in the core pipeline.
- Tests cover CLI, services, GUI workspaces, dialogs, table synchronization, and task lifecycle.

### Maintainability concerns

- `StructureBuilder` is approximately 1,200 lines.
- `AlignmentScreen` is approximately 591 lines.
- `main_window.py` contains a confirmed dead `OutlineScreen` of roughly 360 lines.
- `gui/services/assistance.py` is transitively dead with that screen.

These are not release blockers, but the GUI layer is becoming monolithic. Post-1.0 maintenance should remove dead code first and then consider extracting presentation components without changing behavior.

## 4. Testing assessment

### Independently verified

- `python -m compileall` passed for `src` and `tests`.
- Available environment result: **68 passed, 9 skipped**.
- All skips were GUI modules requiring PySide6.
- No failures occurred in the runnable core/service/CLI subset.

### Not independently reproduced here

The repository reports 213/213 passing from a fresh GUI environment. This audit could not reproduce that exact result because:

- PySide6 was not installed in the audit runtime.
- An attempted fresh editable installation failed because the available package index could not provide the declared build dependency `setuptools>=69`.

This failure is environmental rather than proof of a project defect. Still, for a release artifact, reproducible installation should not depend on undocumented package-index conditions. A wheelhouse, lock/constraints file, or CI record would strengthen the claim.

### Test-quality judgment

Claude's retrospective observation—that the suite primarily supplied confidence while real defects were often discovered through reasoning and real-GUI interaction—is credible. This is not a criticism of the suite. GUI tests frequently function best as regression locks after exploratory and interaction testing reveal the defect. The project correctly combined both methods.

## 5. Documentation assessment

### Strong points

- Operator Manual, GUI guide, architecture, governance, developer handover, sprint log, known issues, checklist, and release-candidate report form a strong knowledge-transfer set.
- The docs clearly distinguish operator workflow from maintainer guidance.
- Known limitations are generally surfaced honestly.
- The release report does not conceal the absence of Git or a license.

### Defects found independently

1. `README.md` links to:
   - `docs/BOOKCORPUSBUILDER_Operator_Manual_v0.2.1.docx`
   - `docs/BOOKCORPUSBUILDER_Brochure.docx`

   Neither file exists in the submitted archive.

2. README states the UX Sprint Summary covers “Sprints 1–16,” while the summary itself includes the release-preparation stage through Sprint 18.

3. The release notes remain named `Release_Notes_v1.0_DRAFT.md`, which is appropriate for RC status but must be resolved or explicitly retained at final release.

4. The operator manual honestly identifies application version 0.2.1, while release materials recommend v1.0.0-rc1. This is transparent but demonstrates that version promotion is incomplete.

## 6. Governance assessment

The governance model is unusually strong for a small research desktop project:

- architecture freeze,
- bounded feature acceptance,
- future-ideas parking lot,
- explicit workspace freeze policy,
- amendment log,
- sprint traceability.

The authoritative repository currently freezes only:

- Workspace 2 — Structure Builder,
- Workspace 3 — Page Alignment.

Earlier conversational descriptions that Workspaces 1, 5, and 7 were also frozen are not reflected in `docs/GOVERNANCE.md`. The repository record should be treated as authoritative. This is not necessarily a defect: the governance document explicitly says freeze status must not be inferred.

## 7. Release-package hygiene

### High-priority defects

#### A. Local configuration leaked into the audit archive

`.bookcorpusbuilder.local.json` contains absolute paths such as:

- `/media/ambijat/SOPRANO2/GPT_workflow/BOOKCORPUSBUILDER`
- local input, outline, and output paths
- serialized UI state

This file is explicitly ignored by `.gitignore` and should not have been packaged. It is both a portability problem and an avoidable disclosure of local-machine details.

#### B. IDE metadata leaked into the archive

`.idea/workspace.xml` contains another absolute local path:

`/media/ambijat/FIGHTER/GPT_WORFLOW2/my_research_assistant`

The complete `.idea/` directory should be excluded from a release/audit distribution unless the package is intentionally a private forensic snapshot.

#### C. Version mismatch

- Archive/report identity: `v1.0.0-rc1`
- `pyproject.toml`: `0.2.1`
- `src/bookcorpusbuilder/__init__.py`: `0.2.1`

A release candidate should have one canonical version, ideally `1.0.0rc1` in Python package metadata and `v1.0.0-rc1` as the Git tag/release label.

#### D. No LICENSE

A distribution outside the current private environment should not proceed until the owner chooses a license or explicitly marks the project proprietary/internal.

#### E. No version control

Without Git, there is no immutable source checkpoint, tag, diff, rollback, or auditable release boundary.

## 8. Security and data-integrity assessment

No obvious dangerous patterns were found in the live source:

- no `eval`, dynamic code execution, unsafe deserialization, or shell execution,
- subprocess use is limited to explicit TTS/ffmpeg commands with argument lists,
- atomic file writes are used in key persistence services,
- extraction temporary directories are cleaned on cancellation/failure,
- duplicate PDFs are hash-detected,
- approved mapping is required for GUI extraction.

The chief risk is operational rather than exploit-oriented: accidental distribution of local configuration, copyrighted PDFs, or generated corpus outputs. The submitted audit ZIP correctly excluded the production PDFs and live corpus data, but failed to exclude local config and IDE metadata.

## 9. Retrospective evidence

The supplied retrospective summary adds useful process evidence:

- The sprint model was effective but occasionally overextended into pixel-level perfection.
- Some cross-cutting decisions should have been surfaced rather than resolved unilaterally.
- The absence of version control remaining undiscovered until Sprint 18 demonstrates the need for periodic release-readiness checkpoints.
- Real-GUI verification and reasoning discovered more defects than the regression suite; tests then protected the fixes.

This is a credible and valuable self-critique. However, `docs/RETROSPECTIVE_ENGINEERING_REPORT.md` was not present in the submitted archive, so the complete retrospective could not be independently reviewed in this audit. It should be added to the next package.

## 10. Required actions before public v1.0.0

### Must complete

1. Decide repository scope and initialize Git.
2. Add a license or an explicit proprietary/internal-use notice.
3. Align version metadata to `1.0.0rc1` before creating the RC tag.
4. Regenerate the audit/release ZIP excluding:
   - `.bookcorpusbuilder.local.json`
   - `.idea/`
   - caches and machine-local state.
5. Fix README's two broken DOCX links.
6. Include `docs/RETROSPECTIVE_ENGINEERING_REPORT.md` in the knowledge-transfer set.
7. Run the full 213-test suite in the intended GUI environment and save the result as a machine-readable release artifact.

### Strongly recommended

8. Add a dependency constraints/lock strategy or publish a tested wheel.
9. Regenerate current DOCX/PDF operator documentation from the final Markdown.
10. Add a CI workflow once Git is initialized.
11. Clarify in `IMPROVEMENT_ROADMAP.md` that legacy CLI page-risk findings do not describe the verified GUI extraction path.
12. Remove confirmed dead code in a post-RC patch, not before the first immutable checkpoint unless separately approved.

## 11. Final independent recommendation

### Private/internal use

**GO.** The application is mature enough for routine internal operation, subject to the documented layout limitation and OCR omission.

### Release candidate shared with a trusted auditor

**CONDITIONAL GO.** The submitted ZIP is usable for technical review, but it should be regenerated because it contains local configuration and IDE metadata.

### Public/external v1.0.0 release

**NO-GO until the seven must-complete actions above are closed.**

### Version recommendation

After those corrections:

1. Set package version to `1.0.0rc1`.
2. Commit and tag `v1.0.0-rc1`.
3. Perform clean-install and full-GUI regression verification.
4. Promote to `1.0.0` only after a short RC operating period or an independent clean-machine sign-off.

