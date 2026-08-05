# Future Ideas — v2 (Deferred / Experimental)

This is the exclusive parking lot for concepts that fail the v1 feature
acceptance rule in `GOVERNANCE.md` — specifically, anything that would
introduce a new conceptual model or a new workspace. Recording an idea here
means: **recorded, not implemented.** Nothing in this document should be
built against the v1 production branch without first revising `GOVERNANCE.md`
to explicitly move BOOKCORPUSBUILDER into a v2 phase.

When a new idea comes up in conversation, the correct response is to add an
entry here, not to start writing code.

---

## Entry format

```text
### <Idea name>
Recorded: <date>
Fails governance rule(s): <1-5 from GOVERNANCE.md, or "new workspace">
Summary: <one paragraph>
```

---

## Page Alignment Assistant (automatic detection tier)

Recorded: 2026-08-04
Fails governance rule(s): 2 (new conceptual model — confidence-scored
detection), 5 (cannot be explained in one paragraph without introducing
detection/confidence semantics to the operator)

Summary: automatic chapter-heading search across native PDF text (exact,
case-insensitive, normalized-whitespace, Roman/Arabic numeral matching),
automatic anchor suggestion with a confidence score derived from deterministic
evidence (exact match, page-top position, chapter-number agreement,
uniqueness, repeated-header penalty), a suggested-anchor accept/reject
workflow, an interactive printed-vs-physical mapping graph, and batch
verification that lets confirmed chapter-level segments cover their
analytical subsections without individual anchors. The v1 Page Alignment
screen already ships a deterministic, arithmetic-only "Suggest Next Anchor"
that points the operator at the next *uncovered* entry without searching PDF
text or scoring confidence — that part stays in v1. The text-search/confidence
engine itself is the part deferred here.

## Corpus Intelligence Layer

Recorded: 2026-08-04
Fails governance rule(s): 2, 3 (would need at least one new workspace —
"Research Workspace"), 5

Summary: named-entity recognition, topic modeling, cross-reference detection,
a citation network, and a knowledge graph built from the extracted corpus.
Would require new ML/NLP dependencies and, per the project's own
AI-optionality philosophy (`docs/ONTOLOGICAL_BASIS.md` — "AI is optional",
"never allow AI output directly into extraction"), a full
candidate-\>schema-validation-\>human-review pipeline before any
entity/topic/relationship could be treated as fact, mirroring how outline
detection already works. Not scoped or designed; this entry is a placeholder
for that future design conversation, not a spec.

## OCR intelligence

Recorded: 2026-08-04
Fails governance rule(s): 2

Summary: automatic OCR for scanned/non-native-text PDFs (currently flagged as
`likely-scanned` and left for the operator to handle outside the tool). Would
introduce a new extraction coordinate space (OCR-inferred text position) and
a new confidence/accuracy concept the operator would need to reason about.

## Semantic search expansion

Recorded: 2026-08-04
Fails governance rule(s): 2

Summary: embedding-based or fuzzy/semantic search over the corpus, beyond the
current deterministic substring search in the Corpus Browser
(`gui/services/search.py`). Deferred because it introduces a non-deterministic
ranking model into a tool whose value proposition is exact, auditable
provenance.

## Workflow redesign / new workspaces generally

Recorded: 2026-08-04
Fails governance rule(s): 3

Summary: any future proposal that would add an eighth workspace, or
restructure the Import → Structure → Verify Mapping → Extract → Browse flow
itself, belongs here by default. The seven-workspace architecture is a frozen
contract per `GOVERNANCE.md` §1.
