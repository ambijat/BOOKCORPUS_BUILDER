import json

import pytest

from bookcorpusbuilder.gui.services.json_outline_importer import (
    JsonOutlineImportError,
    JsonOutlineImporter,
)


def import_document(document):
    return JsonOutlineImporter().import_text(json.dumps(document))


def diagnostic_codes(result):
    return [item.code for item in result.diagnostics]


def test_valid_flat_json_preserves_schema_source_and_hash():
    result = import_document([{
        "sno": "1",
        "title": "Perspective",
        "kind": "chapter",
        "printed_start": 1,
        "level": 1,
        "parent_sno": None,
        "source": "manual_json",
        "include": True,
    }])

    candidate = result.candidates[0]
    assert candidate.source_sno == "1"
    assert candidate.title == "Perspective"
    assert candidate.source == "manual_json"
    assert candidate.include is True
    assert candidate.raw_import_hash == result.import_hash
    assert len(result.import_hash) == 64
    assert result.diagnostics == []


def test_physical_start_and_pdf_index_are_imported():
    """Regression test: physical_start and pdf_index were present in the source JSON and
    fetchable from the book, but ROW_KEYS didn't include them, so the importer silently
    dropped both onto the unknown_key diagnostic path on every row instead of retaining
    them on the candidate."""
    result = import_document([{
        "sno": "3", "title": "Chapter One: Life as a Work of Art", "kind": "chapter",
        "level": 1, "printed_start": 27, "physical_start": 47, "pdf_index": 46,
    }])

    assert diagnostic_codes(result).count("unknown_key") == 0
    candidate = result.candidates[0]
    assert candidate.physical_start == 47
    assert candidate.pdf_page_index == 46

    entry = candidate.to_outline_entry(fallback_sno=1)
    assert entry.physical_start == 47
    assert entry.pdf_page_index == 46


def test_invalid_physical_start_and_pdf_index_are_flagged():
    result = import_document([{
        "sno": "1", "title": "Bad coordinates", "kind": "chapter",
        "level": 1, "printed_start": 1, "physical_start": "not a number", "pdf_index": -5,
    }])

    assert "invalid_physical_start" in diagnostic_codes(result)
    assert "invalid_pdf_index" in diagnostic_codes(result)
    candidate = result.candidates[0]
    assert candidate.physical_start is None
    assert candidate.pdf_page_index is None
    assert candidate.include is False


def test_pdf_index_not_matching_physical_start_minus_one_is_flagged():
    result = import_document([{
        "sno": "1", "title": "Mismatched coordinates", "kind": "chapter",
        "level": 1, "printed_start": 1, "physical_start": 10, "pdf_index": 5,
    }])

    assert "pdf_index_mismatch" in diagnostic_codes(result)
    candidate = result.candidates[0]
    # The individually-valid values are still retained -- only the relationship is flagged.
    assert candidate.physical_start == 10
    assert candidate.pdf_page_index == 5
    assert candidate.include is False


def test_valid_nested_document_keeps_book_metadata():
    result = import_document({
        "book": {"title": "Democratic Ideals and Reality", "author": "Halford J. Mackinder"},
        "outline": [{
            "sno": "1", "title": "Perspective", "kind": "chapter",
            "printed_start": 1, "level": 1, "parent_sno": None, "children": [],
        }],
    })

    assert result.book_metadata == {
        "title": "Democratic Ideals and Reality",
        "author": "Halford J. Mackinder",
    }
    assert [row.title for row in result.candidates] == ["Perspective"]
    assert result.candidates[0].source == "imported_json"


def test_recursive_children_are_flattened_with_hierarchy():
    result = import_document({"outline": [{
        "sno": "1", "title": "Part One", "kind": "part", "printed_start": 1,
        "level": 1, "parent_sno": None, "children": [{
            "sno": "1.1", "title": "Chapter One", "kind": "chapter", "printed_start": 2,
            "level": 2, "children": [{
                "sno": "1.1.1", "title": "Section One", "kind": "section",
                "printed_start": 3, "level": 3,
            }],
        }],
    }]})

    assert [row.source_sno for row in result.candidates] == ["1", "1.1", "1.1.1"]
    assert [row.parent_sno for row in result.candidates] == ["", "1", "1.1"]
    assert result.candidates[1].parent_candidate_id == result.candidates[0].candidate_id
    assert result.candidates[2].parent_candidate_id == result.candidates[1].candidate_id


def test_duplicate_sno_is_reported_and_excluded():
    result = import_document([
        {"sno": "1", "title": "First", "kind": "chapter", "printed_start": 1, "level": 1},
        {"sno": "1", "title": "Second", "kind": "chapter", "printed_start": 2, "level": 1},
    ])

    assert diagnostic_codes(result).count("duplicate_sno") == 2
    assert all(row.include is False for row in result.candidates)


def test_orphan_parent_is_reported_and_excluded():
    result = import_document([{
        "sno": "2", "title": "Orphan", "kind": "section", "printed_start": 2,
        "level": 2, "parent_sno": "missing",
    }])

    assert "orphan_parent" in diagnostic_codes(result)
    assert result.candidates[0].include is False


def test_null_printed_start_is_metadata_not_extraction_boundary():
    result = import_document([{
        "sno": "1", "title": "Analytical note", "kind": "notes",
        "printed_start": None, "level": 1, "include": True,
    }])

    candidate = result.candidates[0]
    assert candidate.printed_page is None
    assert "missing_printed_page" in candidate.warning_codes
    assert candidate.include is False


def test_unknown_keys_are_diagnostics_and_never_outline_titles():
    result = import_document({
        "book": {"title": "Book title", "edition": "metadata only"},
        "parent_sno": "document metadata only",
        "outline": [{
            "sno": "1", "title": "Real title", "kind": "chapter",
            "printed_start": 1, "level": 1, "mystery": "not a row",
        }],
    })

    assert diagnostic_codes(result).count("unknown_key") == 3
    assert [row.title for row in result.candidates] == ["Real title"]


def test_malformed_json_is_rejected():
    with pytest.raises(JsonOutlineImportError, match="Malformed JSON"):
        JsonOutlineImporter().import_text('[{"sno": "1"}')


def test_all_row_validation_rules_are_applied():
    result = import_document([{
        "sno": "", "title": "", "kind": "made-up", "printed_start": 1.5,
        "level": 0, "include": "yes", "source": "",
    }])

    assert {
        "missing_sno", "missing_title", "invalid_kind", "invalid_printed_page",
        "invalid_level", "invalid_include", "invalid_source",
    }.issubset(set(diagnostic_codes(result)))
    assert result.candidates[0].include is False


def test_roman_printed_start_is_valid_and_retained_as_label():
    result = import_document([{
        "sno": "P", "title": "Preface", "kind": "section",
        "printed_start": "vii", "level": 1,
    }])

    assert result.error_count == 0
    assert result.candidates[0].printed_page_label == "vii"
    assert "roman_page" in result.candidates[0].warning_codes
