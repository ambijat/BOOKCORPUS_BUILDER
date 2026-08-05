import csv
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bookcorpusbuilder.extract import Row, main as extract_main, read_outline_csv, resolve_physical_pages
from bookcorpusbuilder.gui.models import MappingAnchor, PageMapping
from bookcorpusbuilder.gui.services.common import sha256_file, stable_book_id
from bookcorpusbuilder.gui.services.mapping import MappingService
from bookcorpusbuilder.outline import OutlineItem, write_csv_template


class ReadOutlineCsvTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temporary.name) / "outline.csv"

    def tearDown(self):
        self.temporary.cleanup()

    def _write(self, header, rows):
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

    def test_legacy_printed_start_only_csv_still_reads(self):
        self._write(["Sno", "title", "printed_start"], [[1, "Intro", 3]])
        rows = read_outline_csv(self.csv_path)
        self.assertEqual(rows, [Row(sno=1, title="Intro", start=3, already_physical=False)])

    def test_physical_start_column_is_read_as_already_physical(self):
        self._write(["Sno", "title", "printed_start", "physical_start"], [[1, "Heading", "", 9]])
        rows = read_outline_csv(self.csv_path)
        self.assertEqual(rows, [Row(sno=1, title="Heading", start=9, already_physical=True)])

    def test_printed_start_takes_precedence_when_both_present(self):
        self._write(["Sno", "title", "printed_start", "physical_start"], [[1, "Both", 3, 9]])
        rows = read_outline_csv(self.csv_path)
        self.assertFalse(rows[0].already_physical)
        self.assertEqual(rows[0].start, 3)


class ResolvePhysicalPagesTests(unittest.TestCase):
    def test_already_physical_rows_pass_through(self):
        rows = [Row(sno=1, title="Heading", start=9, end=12, already_physical=True)]
        unresolved = resolve_physical_pages(rows, PageMapping("book"))
        self.assertEqual(unresolved, [])
        self.assertEqual((rows[0].physical_start, rows[0].physical_end), (9, 12))

    def test_printed_rows_resolve_through_mapping(self):
        mapping = PageMapping("book", [MappingAnchor(1, 3, 2, "a"), MappingAnchor(2, 4, 3, "b")])
        rows = [Row(sno=1, title="Intro", start=1, end=1)]
        unresolved = resolve_physical_pages(rows, mapping)
        self.assertEqual(unresolved, [])
        self.assertEqual((rows[0].physical_start, rows[0].physical_end), (3, 3))

    def test_unresolvable_rows_are_reported_not_silently_extracted(self):
        mapping = PageMapping("book", [MappingAnchor(1, 3, 2, "a"), MappingAnchor(2, 4, 3, "b"),
                                        MappingAnchor(1000, 1500, 1499, "c"), MappingAnchor(1010, 1510, 1509, "d")])
        rows = [Row(sno=1, title="Gap section", start=500, end=500)]
        unresolved = resolve_physical_pages(rows, mapping)
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].row.sno, 1)
        self.assertTrue(unresolved[0].reason)


def _fake_pdfplumber_module(page_texts):
    pages = [SimpleNamespace(extract_text=lambda t=text: t) for text in page_texts]

    class _Pdf:
        def __enter__(self_inner):
            return SimpleNamespace(pages=pages)

        def __exit__(self_inner, *_args):
            return False

    return SimpleNamespace(open=lambda *_args, **_kwargs: _Pdf())


class ExtractCliGatingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.input_dir = self.root / "input"; self.input_dir.mkdir()
        self.outline_dir = self.root / "outlines"; self.outline_dir.mkdir()
        self.output_dir = self.root / "output"
        self.pdf_path = self.input_dir / "book.pdf"
        self.pdf_path.write_bytes(b"fake pdf bytes")
        self.book_id = stable_book_id(sha256_file(self.pdf_path))
        self.outline_csv = self.outline_dir / "book_outline_clean.csv"
        with self.outline_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Sno", "title", "printed_start", "physical_start"])
            writer.writerow([1, "Intro", 1, ""])
            writer.writerow([2, "Chapter", 2, ""])
        self.argv = [
            "bookcorpus-extract", "--outline", str(self.outline_csv),
            "--pdf", str(self.pdf_path), "--out", str(self.output_dir),
        ]

    def tearDown(self):
        self.temporary.cleanup()

    def _run(self, page_texts):
        fake_module = _fake_pdfplumber_module(page_texts)
        with patch.object(sys, "argv", self.argv), \
             patch.dict(sys.modules, {"pdfplumber": fake_module}), \
             patch("bookcorpusbuilder.extract.OUTLINE_DIR", self.outline_dir):
            extract_main()

    def test_refuses_to_run_without_an_approved_mapping(self):
        with self.assertRaises(SystemExit):
            self._run(["p1", "p2", "p3", "p4", "p5", "p6"])
        self.assertEqual(list((self.output_dir / "manifests").glob("*.csv")), [])

    def test_runs_and_records_physical_pages_once_mapping_is_approved(self):
        mapping = PageMapping(self.book_id, [MappingAnchor(1, 3, 2, "a"), MappingAnchor(2, 4, 3, "b")])
        MappingService(self.outline_dir).approve(mapping, 6)
        self._run(["front", "front2", "intro text", "chapter text", "p5", "p6"])
        manifest = self.output_dir / "manifests" / "book_manifest.csv"
        self.assertTrue(manifest.exists())
        rows = {row["Sno"]: row for row in csv.DictReader(manifest.open(encoding="utf-8"))}
        self.assertEqual(rows["1"]["physical_start"], "3")
        self.assertEqual(rows["2"]["physical_start"], "4")


class OutlineCsvCoordinateSeparationTests(unittest.TestCase):
    def test_toc_and_heading_pages_are_never_written_to_the_same_column(self):
        items = [
            OutlineItem(title="Chapter 1", printed_start=12, kind="toc"),
            OutlineItem(title="Chapter 1", printed_start=14, y=1.0, kind="heading"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            out_csv = Path(directory) / "outline.csv"
            write_csv_template(items, out_csv, include_end=False, max_page=200)
            rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
        self.assertEqual(rows[0]["kind"], "toc")
        self.assertEqual(rows[0]["printed_start"], "12")
        self.assertEqual(rows[0]["physical_start"], "")
        self.assertEqual(rows[1]["kind"], "heading")
        self.assertEqual(rows[1]["printed_start"], "")
        self.assertEqual(rows[1]["physical_start"], "14")


if __name__ == "__main__":
    unittest.main()
