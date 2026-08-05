import tempfile
import unittest
from pathlib import Path

from bookcorpusbuilder.extract import Row, compute_page_ranges, infer_pdf_from_outline
from bookcorpusbuilder.paths import INPUT_PDF_DIR, PROJECT_ROOT


class ArchitectureTests(unittest.TestCase):
    def test_canonical_input_path_is_repository_anchored(self):
        self.assertEqual(INPUT_PDF_DIR, PROJECT_ROOT / "data" / "input" / "pdfs")

    def test_repeated_outline_starts_share_the_next_distinct_range(self):
        rows = [Row(1, "Part", 3), Row(2, "Chapter", 3), Row(3, "Next", 8)]
        ranged = compute_page_ranges(rows, max_page=20)
        self.assertEqual([(row.start, row.end) for row in ranged], [(3, 7), (3, 7), (8, 20)])

    def test_inference_does_not_search_the_callers_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            outline = Path(directory) / "missing_book_outline_clean.csv"
            self.assertIsNone(infer_pdf_from_outline(outline))


if __name__ == "__main__":
    unittest.main()
