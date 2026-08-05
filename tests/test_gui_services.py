import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from bookcorpusbuilder.gui.models import BookRecord, MappingAnchor, OutlineEntry, PageMapping, Severity
from bookcorpusbuilder.gui.services.common import sha256_file, stable_book_id
from bookcorpusbuilder.gui.services.extraction import ExtractionService
from bookcorpusbuilder.gui.services.history import HistoryService
from bookcorpusbuilder.gui.services.library import DuplicateBookError, LibraryImportError, LibraryService
from bookcorpusbuilder.gui.services.mapping import MappingService, SUGGESTED_ACTION, suggested_action
from bookcorpusbuilder.gui.services.outline_text_parser import OutlineMergeService, OutlineTextParser
from bookcorpusbuilder.gui.services.outlines import OutlineService
from bookcorpusbuilder.gui.services.search import CorpusSearchService
from bookcorpusbuilder.gui.services.settings import SettingsService
from bookcorpusbuilder.gui.services.validation import preflight


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakePdf:
    def __init__(self, texts):
        self.pages = [FakePage(text) for text in texts]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class GuiServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "input"
        self.outlines_dir = self.root / "outlines"
        self.outputs = self.root / "output"
        self.source = self.root / "source.pdf"
        self.source.write_bytes(b"deterministic fake pdf")
        self.digest = sha256_file(self.source)
        self.book = BookRecord(stable_book_id(self.digest), "source.pdf", str(self.source), self.digest, self.source.stat().st_size, 4, "text-extractable")
        self.outlines = OutlineService(self.outlines_dir)
        self.mappings = MappingService(self.outlines_dir)
        self.history = HistoryService(self.outputs / "run_history")

    def tearDown(self):
        self.temporary.cleanup()

    def test_service_layer_imports_without_qt(self):
        self.assertTrue(callable(preflight))

    def test_settings_path_can_be_isolated_for_acceptance(self):
        isolated = self.root / "settings.json"
        with patch.dict(os.environ, {"BOOKCORPUSBUILDER_CONFIG": str(isolated)}):
            self.assertEqual(SettingsService().path, isolated)

    def test_stable_identity_and_duplicate_detection(self):
        library = LibraryService(self.inputs, self.outlines_dir / "library.json")
        with patch.object(library, "_inspect_pdf", return_value=(4, "text-extractable")):
            first = library.add(self.source)
            self.assertEqual(first.book_id, stable_book_id(self.digest))
            with self.assertRaises(DuplicateBookError):
                library.add(self.source)

    def test_same_filename_stem_different_content_has_distinct_id(self):
        other_dir = self.root / "other"; other_dir.mkdir()
        other = other_dir / "source.pdf"; other.write_bytes(b"different")
        self.assertNotEqual(stable_book_id(sha256_file(other)), self.book.book_id)

    def test_blank_native_extraction_is_marked_likely_scanned(self):
        library = LibraryService(self.inputs, self.outlines_dir / "library.json")
        fake_module = SimpleNamespace(open=lambda *_args, **_kwargs: FakePdf(["", "", ""]))
        with patch.dict(sys.modules, {"pdfplumber": fake_module}):
            pages, status = library._inspect_pdf(self.source)
        self.assertEqual(pages, 3)
        self.assertEqual(status, "likely-scanned")

    def test_readding_a_removed_registration_restores_it_rather_than_rejecting(self):
        # Root cause of the "Add PDFs does nothing" bug: remove_registration()
        # only hides a book_id, it never deletes it from state["books"]. The
        # old add() treated "still present" as a duplicate regardless of
        # hidden state, so re-adding a removed book raised DuplicateBookError
        # -- which the UI only ever surfaced as a 5s status-bar toast, giving
        # no way back in for a book the operator can no longer even see.
        library = LibraryService(self.inputs, self.outlines_dir / "library.json")
        with patch.object(library, "_inspect_pdf", return_value=(4, "text-extractable")):
            first = library.add(self.source)
            library.remove_registration(first.book_id)
            self.assertEqual(library.books(), [])

            restored = library.add(self.source)
            self.assertEqual(restored.book_id, first.book_id)
            self.assertEqual([book.book_id for book in library.books()], [first.book_id])

    def test_copy_failure_raises_library_import_error_and_leaves_no_trace(self):
        library = LibraryService(self.inputs, self.outlines_dir / "library.json")
        with patch("bookcorpusbuilder.gui.services.library.shutil.copy2", side_effect=OSError("disk full")):
            with self.assertRaises(LibraryImportError) as ctx:
                library.add(self.source)
        self.assertEqual(ctx.exception.stage, "copying into library")
        self.assertFalse((self.inputs / self.source.name).exists())
        self.assertFalse(list(self.inputs.glob(".*.importing")))
        self.assertEqual(library._load()["books"], {})

    def test_registry_write_failure_raises_library_import_error_and_leaves_no_trace(self):
        library = LibraryService(self.inputs, self.outlines_dir / "library.json")
        with patch.object(library, "_inspect_pdf", return_value=(4, "text-extractable")):
            with patch.object(library, "_save", side_effect=OSError("permission denied")):
                with self.assertRaises(LibraryImportError) as ctx:
                    library.add(self.source)
        self.assertEqual(ctx.exception.stage, "saving registry")
        self.assertFalse((self.inputs / self.source.name).exists())
        self.assertFalse(list(self.inputs.glob(".*.importing")))
        self.assertFalse((self.outlines_dir / "library.json").exists())

    def test_finalize_failure_rolls_back_registry_and_leaves_no_orphan_pdf(self):
        library = LibraryService(self.inputs, self.outlines_dir / "library.json")
        with patch.object(library, "_inspect_pdf", return_value=(4, "text-extractable")):
            with patch("bookcorpusbuilder.gui.services.library.Path.replace", side_effect=OSError("cross-device link")):
                with self.assertRaises(LibraryImportError) as ctx:
                    library.add(self.source)
        self.assertEqual(ctx.exception.stage, "finalizing import")
        self.assertFalse((self.inputs / self.source.name).exists())
        self.assertFalse(list(self.inputs.glob(".*.importing")))
        self.assertEqual(library._load()["books"], {})

    def test_not_a_pdf_and_missing_source_are_reported_as_validation_failures(self):
        library = LibraryService(self.inputs, self.outlines_dir / "library.json")
        missing = self.root / "does-not-exist.pdf"
        with self.assertRaises(LibraryImportError) as ctx:
            library.add(missing)
        self.assertEqual(ctx.exception.stage, "validating source")

        not_a_pdf = self.root / "notes.txt"
        not_a_pdf.write_text("not a pdf")
        with self.assertRaises(LibraryImportError) as ctx:
            library.add(not_a_pdf)
        self.assertEqual(ctx.exception.stage, "validating source")

    def test_outline_round_trip_and_duplicate_sno(self):
        path = self.outlines_dir / "import.csv"
        entries = [OutlineEntry(1, "One", printed_start=1), OutlineEntry(1, "Two", printed_start=2)]
        self.outlines.save(path, entries)
        loaded = self.outlines.load(path)
        issues = self.outlines.validate(loaded, 4)
        self.assertTrue(any(issue.code == "duplicate_sno" and issue.severity == Severity.BLOCKING for issue in issues))

    def test_pasted_outline_dotted_plain_chapter_and_multiline_formats(self):
        result = OutlineTextParser().parse("""Table of Contents
Chapter One
Perspective .......... 3
2. A deliberately long title
continued on the next copied line 18
Further reading
225
""")
        included = [item for item in result.candidates if item.include]
        self.assertEqual(
            [(item.title, item.kind, item.printed_page) for item in included],
            [
                ("Chapter One Perspective", "chapter", 3),
                ("2. A deliberately long title continued on the next copied line", "section", 18),
                ("Further reading", "section", 225),
            ],
        )
        self.assertEqual(result.candidates[0].warning_codes, ["possible_running_header", "possible_noise"])
        self.assertGreater(included[0].confidence, included[-1].confidence)

    def test_pasted_outline_hierarchy_and_inferred_part_pages(self):
        result = OutlineTextParser().parse("""Part I The Old World
Chapter 1 Perspective 1
Chapter 2 Social Momentum 17
Part II The New World
Chapter 3 The Heartland 45
""")
        self.assertEqual([item.kind for item in result.candidates], ["part", "chapter", "chapter", "part", "chapter"])
        self.assertEqual([item.level for item in result.candidates], [1, 2, 2, 1, 2])
        self.assertEqual([item.printed_page for item in result.candidates], [1, 1, 17, 45, 45])
        self.assertIsNone(result.candidates[0].parent_candidate_id)
        self.assertEqual(result.candidates[1].parent_candidate_id, result.candidates[0].candidate_id)
        self.assertIn("page_inferred_from_child", result.candidates[0].warning_codes)

    def test_pasted_outline_delimiters_roman_pages_and_numeric_headings(self):
        result = OutlineTextParser().parse("""1,Perspective,1
2|The Sea View|24
3\tThe Land View\t48
Preface vii
1.1 Strategic Context 8
""")
        self.assertEqual([item.parser_rule for item in result.candidates[:3]], ["delimited"] * 3)
        self.assertEqual([item.sno for item in result.candidates[:3]], [1, 2, 3])
        self.assertTrue(all(item.sno_explicit for item in result.candidates[:3]))
        self.assertEqual(result.candidates[3].printed_page_label, "vii")
        self.assertIsNone(result.candidates[3].printed_page)
        self.assertIn("roman_page", result.candidates[3].warning_codes)
        self.assertEqual(result.candidates[4].level, 2)

    def test_pipe_delimited_hierarchical_snos_are_provenance_not_titles(self):
        result = OutlineTextParser().parse("""1 | Perspective | 1
1.1 | The Great War as a turning point | 1
1.2 | Geographical opportunity | 2
2 | Social Momentum | 5
2.1 | Liberty, equality and fraternity | 5
""")

        self.assertEqual(
            [item.title for item in result.candidates],
            [
                "Perspective", "The Great War as a turning point",
                "Geographical opportunity", "Social Momentum",
                "Liberty, equality and fraternity",
            ],
        )
        self.assertEqual([item.sno for item in result.candidates], [1, 2, 3, 4, 5])
        self.assertEqual([item.source_sno for item in result.candidates], ["1", "1.1", "1.2", "2", "2.1"])
        self.assertEqual([item.level for item in result.candidates], [1, 2, 2, 1, 2])
        self.assertEqual([item.parent_sno for item in result.candidates], ["", "1", "1", "", "2"])
        self.assertFalse(any("duplicate_sno" in item.warning_codes for item in result.candidates))

    def test_pasted_outline_empty_ambiguous_noise_and_duplicates_are_retained(self):
        self.assertEqual(OutlineTextParser().parse("").candidates, [])
        result = OutlineTextParser().parse("CONTENTS\nRUNNING HEADER\nRUNNING HEADER\nPerspective .... 1\nPerspective .... 1")
        self.assertFalse(result.candidates[0].include)
        self.assertTrue(any("ambiguous_page" in item.warning_codes for item in result.candidates))
        duplicates = [item for item in result.candidates if "duplicate_title" in item.warning_codes]
        self.assertGreaterEqual(len(duplicates), 2)

    def test_candidate_editing_exclusion_and_provenance_survive_conversion(self):
        candidate = OutlineTextParser().parse("Perspective 1").candidates[0]
        candidate.title = "Edited Perspective"
        candidate.include = False
        candidate.edited_by_user = True
        entry = candidate.to_outline_entry(1)
        self.assertEqual(entry.source, "pasted_outline")
        self.assertTrue(entry.edited_by_user)
        self.assertFalse(entry.include)
        self.assertEqual(entry.title, "Edited Perspective")

    def test_merge_matching_conflicting_and_excluded_candidates(self):
        draft = [OutlineEntry(1, "Perspective", "chapter", 4, level=1)]
        candidates = OutlineTextParser().parse("Perspective 1\nNew Chapter 9\nIgnored 12").candidates
        candidates[-1].include = False
        analysis = OutlineMergeService().analyse(draft, candidates)
        self.assertEqual(len(analysis.conflicting_rows), 1)
        self.assertEqual(len(analysis.new_rows), 1)
        self.assertEqual(len(analysis.ignored_rows), 1)
        conservative = OutlineMergeService().apply(draft, analysis)
        self.assertEqual(conservative[0].printed_start, 4)
        use_candidate = OutlineMergeService().apply(draft, analysis, {candidates[0].candidate_id: "use_candidate"})
        self.assertEqual(use_candidate[0].printed_start, 1)

    def test_approved_outline_cannot_be_replaced_without_revocation(self):
        entries = [OutlineEntry(1, "Perspective", printed_start=1)]
        self.outlines.approve(self.book, entries, "accepted")
        with self.assertRaises(FileExistsError):
            self.outlines.approve(self.book, [OutlineEntry(1, "Replacement", printed_start=2)])

    def test_offset_conversion_and_conflict(self):
        mapping = PageMapping(self.book.book_id, [MappingAnchor(1, 3, 2), MappingAnchor(10, 12, 11)])
        self.assertEqual(mapping.offset, 2)
        self.assertEqual(mapping.physical_for(7), 9)
        self.assertFalse(any(issue.severity == Severity.BLOCKING for issue in self.mappings.validate(mapping, 20)))
        # A second anchor at a page that already has a confirmed anchor, disagreeing
        # on the physical page, is a genuine same-page contradiction.
        mapping.anchors.append(MappingAnchor(1, 4, 3, "Recheck"))
        self.assertTrue(any(issue.code == "offset_conflict" for issue in self.mappings.validate(mapping, 20)))

    def test_differing_offsets_at_different_pages_are_unconfirmed_not_conflicting(self):
        # Two isolated anchors with different implied offsets describe two
        # candidate segments, each backed by only one anchor — that needs a
        # second confirming anchor per segment, it isn't a contradiction.
        mapping = PageMapping(self.book.book_id, [MappingAnchor(1, 3, 2), MappingAnchor(10, 13, 12)])
        issues = self.mappings.validate(mapping, 20)
        self.assertFalse(any(issue.code == "offset_conflict" for issue in issues))
        self.assertTrue(any(issue.code == "segment_unconfirmed" for issue in issues))
        self.assertTrue(any(issue.code == "offset_unresolved" for issue in issues))

    def test_out_of_range_mapping_is_blocked(self):
        mapping = PageMapping(self.book.book_id, [MappingAnchor(1, 3, 2), MappingAnchor(2, 9, 8)])
        self.assertTrue(any(issue.code == "anchor_out_of_range" for issue in self.mappings.validate(mapping, 4)))

    def test_segmented_mapping_resolves_front_matter_and_body_independently(self):
        # Roman-numeral front matter (offset +2) followed by a body with a
        # different fixed offset (+10) — the common real-book case that a
        # single global offset cannot represent.
        mapping = PageMapping(self.book.book_id, [
            MappingAnchor(1, 3, 2, "front i"), MappingAnchor(5, 7, 6, "front v"),
            MappingAnchor(1000, 1010, 1009, "body 1000"), MappingAnchor(1010, 1020, 1019, "body 1010"),
        ])
        issues = self.mappings.validate(mapping, 2000)
        self.assertFalse(any(issue.severity == Severity.BLOCKING for issue in issues))
        self.assertEqual(len(mapping.confirmed_segments()), 2)
        self.assertEqual(mapping.physical_for(3), 5)  # inside front-matter segment
        self.assertEqual(mapping.physical_for(1005), 1015)  # inside body segment
        gap = mapping.resolve(500)  # between the two segments, covered by neither
        self.assertIsNone(gap.physical_page)
        self.assertEqual(gap.method, "unresolved")

    def test_uncovered_entry_blocks_approval(self):
        entries = [
            OutlineEntry(1, "Front", printed_start=3),
            OutlineEntry(2, "Gap section", printed_start=500),
        ]
        mapping = PageMapping(self.book.book_id, [
            MappingAnchor(1, 3, 2, "front i"), MappingAnchor(5, 7, 6, "front v"),
            MappingAnchor(1000, 1010, 1009, "body 1000"), MappingAnchor(1010, 1020, 1019, "body 1010"),
        ])
        issues = self.mappings.validate(mapping, 2000, entries)
        self.assertTrue(any(issue.code == "uncovered_entry" for issue in issues))
        with self.assertRaises(ValueError):
            self.mappings.approve(mapping, 2000, "test", entries)

    def test_entries_with_supplied_physical_start_do_not_require_anchors(self):
        """Regression test: entries carrying their own self-consistent physical_start/
        pdf_page_index (e.g. from JSON import) are the strongest available evidence for
        their own physical page and must not be flagged uncovered, nor force the
        two-anchors-required/offset-unresolved gates, just because no anchor happens to
        exist. The Preface entry deliberately has no printed_start (a Roman "ix" page in
        the source JSON, which the importer records as a label, not a number) to also
        cover the "physical_start without printed_start" case."""
        entries = [
            OutlineEntry(1, "Preface", "preface", physical_start=15, pdf_page_index=14),
            OutlineEntry(2, "Chapter One", "chapter", printed_start=27, physical_start=47, pdf_page_index=46),
            OutlineEntry(3, "Section", "section", printed_start=32, physical_start=52, pdf_page_index=51),
        ]
        mapping = PageMapping(self.book.book_id)  # zero anchors
        issues = self.mappings.validate(mapping, 200, entries)
        self.assertFalse(any(issue.severity == Severity.BLOCKING for issue in issues))
        self.assertFalse(any(issue.code == "uncovered_entry" for issue in issues))
        self.assertFalse(any(issue.code == "two_anchors_required" for issue in issues))
        resolution = mapping.resolve_entry(entries[1])
        self.assertEqual(resolution.physical_page, 47)
        self.assertEqual(resolution.method, "supplied")
        self.mappings.approve(mapping, 200, "test", entries)  # must not raise

    def test_entries_with_inconsistent_supplied_coordinates_still_need_anchors(self):
        """A physical_start/pdf_page_index pair that fails pdf_index == physical_start - 1
        is not trustworthy evidence -- resolve_entry() must fall through to anchor-based
        resolution (and therefore still report uncovered_entry / require anchors) rather
        than silently accepting a self-inconsistent supplied mapping."""
        entries = [OutlineEntry(1, "Bad row", "chapter", printed_start=10, physical_start=30, pdf_page_index=99)]
        mapping = PageMapping(self.book.book_id)
        resolution = mapping.resolve_entry(entries[0])
        self.assertNotEqual(resolution.method, "supplied")
        self.assertIsNone(resolution.physical_page)
        issues = self.mappings.validate(mapping, 200, entries)
        self.assertTrue(any(issue.code == "uncovered_entry" for issue in issues))

    def test_extraction_uses_supplied_physical_start_without_any_anchors(self):
        """Critical regression test: before resolve_entry() existed, ExtractionService
        called mapping.physical_for(entry.printed_start), which only consults anchors --
        an entry whose *only* source of physical-page truth was JSON-imported
        physical_start/pdf_page_index resolved to None and silently could not be
        extracted, with zero anchors as the trigger, not just a UI warning."""
        entries = [
            OutlineEntry(1, "First", "chapter", printed_start=1, physical_start=1, pdf_page_index=0),
            OutlineEntry(2, "Second", "chapter", printed_start=3, physical_start=3, pdf_page_index=2),
        ]
        approval = self.outlines.approve(self.book, entries, "test")
        mapping = PageMapping(self.book.book_id)  # zero anchors
        self.mappings.approve(mapping, self.book.page_count, "test", entries)
        service = ExtractionService(self.outputs, self.history, self.outlines, self.mappings)
        fake_module = SimpleNamespace(open=lambda *_args, **_kwargs: FakePdf(["alpha page", "middle", "beta phrase", "last"]))
        with patch.dict(sys.modules, {"pdfplumber": fake_module}):
            result = service.run(self.book, entries, approval, mapping)
        self.assertEqual(result.record.status, "completed")
        self.assertEqual(result.record.written_count, 2)
        self.assertEqual(result.record.failed_count, 0)

    def test_suggested_action_covers_every_validate_code(self):
        mapping = PageMapping(self.book.book_id, [MappingAnchor(1, 3, 2, "a")])
        entries = [OutlineEntry(1, "Gap", printed_start=500)]
        for issue in self.mappings.validate(mapping, 20, entries):
            self.assertIn(issue.code, set(SUGGESTED_ACTION) | {"mapping_valid"})
            if issue.code != "mapping_valid":
                self.assertTrue(suggested_action(issue))

    def test_suggest_next_anchor_prefers_uncovered_chapter_over_section(self):
        # A single anchor with no confirming partner establishes no confirmed
        # segment, so only printed page 1 itself (the anchor's own page) resolves.
        mapping = PageMapping(self.book.book_id, [MappingAnchor(1, 3, 2, "a")])
        entries = [
            OutlineEntry(1, "Covered", "chapter", printed_start=1),
            OutlineEntry(2, "Uncovered section", "section", printed_start=500),
            OutlineEntry(3, "Uncovered chapter", "chapter", printed_start=600),
        ]
        suggestion = self.mappings.suggest_next_anchor(mapping, entries)
        self.assertEqual(suggestion.sno, 3)

    def test_suggest_next_anchor_returns_none_when_fully_resolved(self):
        mapping = PageMapping(self.book.book_id, [MappingAnchor(1, 3, 2, "a"), MappingAnchor(2, 4, 3, "b")])
        entries = [OutlineEntry(1, "Covered", printed_start=1)]
        self.assertIsNone(self.mappings.suggest_next_anchor(mapping, entries))

    def test_non_monotonic_section_starts_are_blocked(self):
        entries = [OutlineEntry(1, "Later", printed_start=3), OutlineEntry(2, "Earlier", printed_start=1)]
        approval = self.outlines.approve(self.book, entries, "test")
        mapping = PageMapping(self.book.book_id, [MappingAnchor(1, 1, 0), MappingAnchor(3, 3, 2)], approved=True)
        self.mappings.approve(mapping, 4)
        issues = preflight(self.book, entries, approval, mapping, self.outlines, self.mappings)
        self.assertTrue(any(issue.code == "non_monotonic_physical" for issue in issues))

    def approved_context(self):
        entries = [OutlineEntry(1, "First", "chapter", 1), OutlineEntry(2, "Second", "chapter", 3)]
        approval = self.outlines.approve(self.book, entries, "test")
        mapping = PageMapping(self.book.book_id, [MappingAnchor(1, 1, 0), MappingAnchor(3, 3, 2)], approved=True)
        self.mappings.approve(mapping, 4)
        return entries, approval, mapping

    def test_approved_outline_edit_invalidates_preflight(self):
        entries, approval, mapping = self.approved_context()
        _, clean, _ = self.outlines.paths(self.book.book_id)
        clean.write_text(clean.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        issues = preflight(self.book, entries, approval, mapping, self.outlines, self.mappings)
        self.assertTrue(any(issue.code == "outline_hash_mismatch" for issue in issues))

    def test_source_hash_mismatch_is_blocked(self):
        entries, approval, mapping = self.approved_context()
        self.source.write_bytes(b"changed")
        issues = preflight(self.book, entries, approval, mapping, self.outlines, self.mappings)
        self.assertTrue(any(issue.code in {"registered_hash_mismatch", "approval_pdf_mismatch"} for issue in issues))

    def test_atomic_extraction_history_search_and_cancellation(self):
        entries, approval, mapping = self.approved_context()
        service = ExtractionService(self.outputs, self.history, self.outlines, self.mappings)
        fake_module = SimpleNamespace(open=lambda *_args, **_kwargs: FakePdf(["alpha page", "middle", "beta phrase", "last"]))
        with patch.dict(sys.modules, {"pdfplumber": fake_module}):
            result = service.run(self.book, entries, approval, mapping)
        self.assertEqual(result.record.status, "completed")
        run_dir = Path(result.record.output_location)
        self.assertTrue(run_dir.is_dir())
        self.assertTrue((run_dir / "jsonl" / f"{self.book.book_id}_sections.jsonl").exists())
        self.assertEqual(self.history.records()[0].run_id, result.record.run_id)
        hits = CorpusSearchService(self.outputs).search("beta phrase", self.book.book_id)
        self.assertEqual(len(hits), 1)
        self.assertTrue(Path(hits[0]["txt_path"]).exists())

        cancelled = Event(); cancelled.set()
        with patch.dict(sys.modules, {"pdfplumber": fake_module}):
            cancelled_result = service.run(self.book, entries, approval, mapping, cancel=cancelled)
        self.assertEqual(cancelled_result.record.status, "cancelled")
        self.assertFalse(bool(cancelled_result.record.output_location))
        temporary_runs = [path for path in (self.outputs / "runs").iterdir() if path.name.startswith(f".{cancelled_result.record.run_id}")]
        self.assertEqual(temporary_runs, [])


if __name__ == "__main__":
    unittest.main()
