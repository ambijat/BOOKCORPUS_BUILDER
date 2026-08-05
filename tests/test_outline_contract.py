import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from bookcorpusbuilder.gui.models import OutlineEntry, Severity
from bookcorpusbuilder.gui.services.json_outline_importer import JsonOutlineImporter
from bookcorpusbuilder.gui.services.outlines import OutlineService
from bookcorpusbuilder.outline_contract import BookOutlineContract
from bookcorpusbuilder.outline_hashing import contract_payload_hash
from bookcorpusbuilder.outline_contract_repository import OutlineContractRepository
from bookcorpusbuilder.outline_validation import lifecycle_state, validate_contract_semantics
from bookcorpusbuilder.ollama_outline_generator import generate_outline_with_ollama


def contract_document():
    return {
        "schema_name": "book_outline_contract",
        "schema_version": "1.0.0",
        "document": {
            "book_id": "book-demo",
            "pdf_filename": "demo.pdf",
            "pdf_sha256": "a" * 64,
            "title": "Demo Book",
            "subtitle": None,
            "author": "Example Author",
            "total_pdf_pages": 20,
        },
        "generation": {
            "method": "human_curated",
            "generator": "operator",
            "model": None,
            "generated_at": None,
            "source_scope": "complete_pdf",
            "source_pages": {"from_pdf_index": 0, "to_pdf_index": 19},
            "prompt_version": None,
        },
        "pagination": {
            "printed_to_physical_mapping_status": "unresolved",
            "default_offset": None,
            "mapping_sidecar": None,
        },
        "entries": [
            {
                "entry_id": "outline-0001",
                "sno": "1",
                "title": "Perspective",
                "kind": "chapter",
                "level": 1,
                "parent_entry_id": None,
                "parent_sno": None,
                "printed_start": {"label": "1", "numeric": 1, "numbering_system": "arabic"},
                "physical_start": None,
                "pdf_page_index": None,
                "boundary": {
                    "status": "verified_printed",
                    "basis": "printed_chapter_heading",
                    "end_inference": "next_included_entry",
                    "allow_extraction": True,
                },
                "provenance": {
                    "source_type": "printed_heading",
                    "source_page_label": "1",
                    "source_pdf_index": 0,
                    "raw_source_text": "Chapter One — PERSPECTIVE",
                    "analytical_or_verbatim": "verbatim",
                },
                "quality": {"confidence": 1.0, "review_status": "reviewed", "warning_codes": []},
                "include": True,
                "notes": None,
            },
            {
                "entry_id": "outline-0002",
                "sno": "1.1",
                "title": "Analytical transition",
                "kind": "analytical_section",
                "level": 2,
                "parent_entry_id": "outline-0001",
                "parent_sno": "1",
                "printed_start": {"label": "1", "numeric": 1, "numbering_system": "arabic"},
                "physical_start": None,
                "pdf_page_index": None,
                "boundary": {
                    "status": "proposed",
                    "basis": "analytical_thematic_transition",
                    "end_inference": "next_included_entry",
                    "allow_extraction": False,
                },
                "provenance": {
                    "source_type": "analytical_derivation",
                    "source_page_label": "1",
                    "source_pdf_index": 0,
                    "raw_source_text": None,
                    "analytical_or_verbatim": "analytical",
                },
                "quality": {
                    "confidence": 0.82,
                    "review_status": "candidate",
                    "warning_codes": ["analytical_heading", "boundary_requires_review"],
                },
                "include": False,
                "notes": "Verify before enabling.",
            },
        ],
        "validation": {
            "status": "not_validated",
            "validated_at": None,
            "validator_version": "1.0.0",
            "errors": [],
            "warnings": [],
        },
        "approval": {
            "status": "draft",
            "approved_at": None,
            "approved_by": None,
            "outline_sha256": None,
        },
    }


def test_contract_is_strict_and_generated_schema_is_current():
    document = contract_document()
    document["entries"][0]["unknown"] = "forbidden"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BookOutlineContract.model_validate(document)

    schema_path = Path(__file__).parents[1] / "schemas" / "book_outline_contract_v1.schema.json"
    stored = json.loads(schema_path.read_text(encoding="utf-8"))
    assert stored == BookOutlineContract.model_json_schema()
    assert stored["additionalProperties"] is False


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda value: value["entries"][1].update(sno="1"), "Duplicate sno"),
        (lambda value: value["entries"][1].update(parent_entry_id="missing"), "Unknown parent_entry_id"),
        (lambda value: value["entries"][1].update(level=3), "Level does not agree"),
        (lambda value: value["entries"][0].update(physical_start=4, pdf_page_index=4), "pdf_page_index"),
    ],
)
def test_contract_relational_and_coordinate_validation(change, message):
    document = contract_document()
    change(document)
    with pytest.raises(ValidationError, match=message):
        BookOutlineContract.model_validate(document)


def test_proposed_analytical_boundary_cannot_enable_extraction():
    document = contract_document()
    document["entries"][1]["include"] = True
    document["entries"][1]["boundary"]["allow_extraction"] = True
    with pytest.raises(ValidationError, match="Unverified analytical boundaries"):
        BookOutlineContract.model_validate(document)


def test_analytical_kind_and_provenance_must_agree():
    document = contract_document()
    document["entries"][1]["kind"] = "section"
    with pytest.raises(ValidationError, match="Analytical provenance"):
        BookOutlineContract.model_validate(document)


def test_source_evidence_gate_checks_verbatim_text_and_page_ranges():
    document = contract_document()
    document["entries"][0]["provenance"]["raw_source_text"] = None
    document["entries"][0]["provenance"]["source_pdf_index"] = 20
    document["generation"]["source_pages"]["to_pdf_index"] = 20
    contract = BookOutlineContract.model_validate(document)
    report = validate_contract_semantics(contract)
    assert {issue.code for issue in report.errors} >= {
        "missing_verbatim_evidence", "source_evidence_out_of_range",
        "source_scope_out_of_range",
    }


def test_contract_hash_and_approved_lifecycle_are_deterministic():
    document = contract_document()
    document["pagination"]["printed_to_physical_mapping_status"] = "verified"
    document["validation"]["status"] = "valid"
    document["approval"]["status"] = "approved"
    contract = BookOutlineContract.model_validate(document)
    contract.approval.outline_sha256 = contract_payload_hash(contract)

    report = validate_contract_semantics(contract)
    assert report.valid
    assert lifecycle_state(contract, report) == "extraction_ready"
    original_hash = contract_payload_hash(contract)
    contract.entries[0].title = "Changed title"
    assert contract_payload_hash(contract) != original_hash


def test_contract_import_populates_preview_and_retains_analytical_metadata():
    result = JsonOutlineImporter().import_text(
        json.dumps(contract_document()),
        expected_book_id="book-demo",
        expected_pdf_sha256="a" * 64,
        expected_pdf_pages=20,
    )

    chapter, analytical = result.candidates
    assert result.contract is not None
    assert result.lifecycle_state == "generated_candidate"
    assert chapter.include is True
    assert chapter.entry_id == "outline-0001"
    assert chapter.allow_extraction is True
    assert analytical.include is False
    assert analytical.kind == "analytical_section"
    assert analytical.parent_entry_id == chapter.entry_id
    assert analytical.parent_candidate_id == chapter.candidate_id
    assert analytical.analytical_or_verbatim == "analytical"
    assert "boundary_requires_review" in analytical.warning_codes
    assert "metadata_only_boundary" in analytical.warning_codes


def test_contract_for_a_different_selected_pdf_is_never_included():
    result = JsonOutlineImporter().import_text(
        json.dumps(contract_document()),
        expected_book_id="another-book",
        expected_pdf_sha256="b" * 64,
        expected_pdf_pages=99,
    )

    assert {item.code for item in result.diagnostics} >= {
        "book_id_mismatch", "pdf_hash_mismatch", "pdf_page_count_mismatch",
    }
    assert all(candidate.include is False for candidate in result.candidates)


def test_unverified_contract_metadata_cannot_become_extraction_boundary(tmp_path):
    service = OutlineService(tmp_path)
    entry = OutlineEntry(
        1, "Analytical metadata", "analytical_section", 1,
        include=True, allow_extraction=False, boundary_status="proposed",
    )
    issues = service.validate([entry], page_count=20)
    assert any(
        issue.code == "boundary_not_extraction_enabled" and issue.severity == Severity.BLOCKING
        for issue in issues
    )


def test_contract_fields_survive_csv_round_trip(tmp_path):
    service = OutlineService(tmp_path)
    path = tmp_path / "outline.csv"
    entry = OutlineEntry(
        1, "Perspective", "chapter", 1,
        source_sno="1", entry_id="outline-0001",
        provenance_source_type="printed_heading",
        analytical_or_verbatim="verbatim",
        boundary_status="verified_printed",
        boundary_basis="printed_chapter_heading",
        allow_extraction=True,
    )
    service.save(path, [entry])
    assert service.load(path)[0] == entry


def test_ollama_generator_uses_schema_and_can_only_return_draft_candidate():
    document = contract_document()
    document["generation"]["method"] = "ollama_structured"
    document["generation"]["generator"] = "ollama"
    captured = {}

    def fake_chat(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(document)))

    with patch.dict(sys.modules, {"ollama": SimpleNamespace(chat=fake_chat)}):
        contract = generate_outline_with_ollama(
            "source text", "local-model", {"book_id": "book-demo"}
        )

    assert contract.approval.status == "draft"
    assert contract.validation.status == "not_validated"
    assert captured["model"] == "local-model"
    assert captured["format"] == BookOutlineContract.model_json_schema()
    assert captured["options"] == {"temperature": 0}
    assert '"book_id": "book-demo"' in captured["messages"][0]["content"]

    unsafe = copy.deepcopy(document)
    unsafe["approval"]["status"] = "reviewed"
    with patch.dict(sys.modules, {"ollama": SimpleNamespace(chat=lambda **_kwargs: SimpleNamespace(message=SimpleNamespace(content=json.dumps(unsafe))))}):
        with pytest.raises(ValueError, match="unvalidated draft candidate"):
            generate_outline_with_ollama("source text")


def test_contract_repository_uses_versioned_stage_files_and_guards_approval(tmp_path):
    repository = OutlineContractRepository(tmp_path)
    candidate = BookOutlineContract.model_validate(contract_document())
    candidate_path = repository.save(candidate, "candidate")
    assert candidate_path == tmp_path / "book-demo" / "outline_candidate.json"
    assert repository.load("book-demo", "candidate") == candidate

    with pytest.raises(ValueError, match="approval.status reviewed"):
        repository.save(candidate, "reviewed")
    with pytest.raises(ValueError, match="valid, mapped, hash-bound"):
        repository.save(candidate, "approved")

    approved_data = contract_document()
    approved_data["pagination"]["printed_to_physical_mapping_status"] = "verified"
    approved_data["validation"]["status"] = "valid"
    approved_data["approval"]["status"] = "approved"
    approved = BookOutlineContract.model_validate(approved_data)
    approved.approval.outline_sha256 = contract_payload_hash(approved)
    approved_path = repository.save(approved, "approved")
    assert approved_path == tmp_path / "book-demo" / "outline_approved.json"
