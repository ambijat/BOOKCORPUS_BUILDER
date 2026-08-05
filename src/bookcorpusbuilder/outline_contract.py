from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEMA_NAME = "book_outline_contract"
SCHEMA_VERSION = "1.0.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class EntryKind(str, Enum):
    PART = "part"
    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"
    ANALYTICAL_SECTION = "analytical_section"
    PREFACE = "preface"
    INTRODUCTION = "introduction"
    APPENDIX = "appendix"
    NOTES = "notes"
    BIBLIOGRAPHY = "bibliography"
    INDEX = "index"
    CAPTION = "caption"
    TOPIC = "topic"
    GLOSSARY = "glossary"
    ACKNOWLEDGEMENT = "acknowledgement"
    OTHER = "other"


class NumberingSystem(str, Enum):
    ARABIC = "arabic"
    ROMAN_LOWER = "roman_lower"
    ROMAN_UPPER = "roman_upper"
    UNNUMBERED = "unnumbered"


class BoundaryStatus(str, Enum):
    PROPOSED = "proposed"
    VERIFIED_PRINTED = "verified_printed"
    VERIFIED_PHYSICAL = "verified_physical"
    REJECTED = "rejected"


class ReviewStatus(str, Enum):
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class PrintedPage(StrictModel):
    label: str | None = None
    numeric: int | None = Field(default=None, ge=1)
    numbering_system: NumberingSystem = NumberingSystem.UNNUMBERED

    @model_validator(mode="after")
    def validate_numbering(self) -> "PrintedPage":
        if self.numbering_system == NumberingSystem.ARABIC and self.numeric is None:
            raise ValueError("Arabic printed pages require numeric")
        if self.numeric is not None and self.numbering_system != NumberingSystem.ARABIC:
            raise ValueError("numeric is only valid for Arabic printed pages")
        if self.numbering_system == NumberingSystem.UNNUMBERED and self.label is not None:
            raise ValueError("Unnumbered pages cannot have a label")
        return self


class Boundary(StrictModel):
    status: BoundaryStatus
    basis: str = Field(min_length=1)
    end_inference: Literal[
        "next_included_entry", "explicit_end", "chapter_end", "unknown",
    ] = "next_included_entry"
    allow_extraction: bool = False


class Provenance(StrictModel):
    source_type: Literal[
        "printed_toc", "printed_heading", "pdf_bookmark",
        "analytical_derivation", "ollama_candidate", "manual",
        "csv_import", "json_import",
    ]
    source_page_label: str | None = None
    source_pdf_index: int | None = Field(default=None, ge=0)
    raw_source_text: str | None = None
    analytical_or_verbatim: Literal["verbatim", "analytical", "mixed"]


class Quality(StrictModel):
    confidence: float = Field(ge=0.0, le=1.0)
    review_status: ReviewStatus
    warning_codes: list[str] = Field(default_factory=list)


class OutlineContractEntry(StrictModel):
    entry_id: str = Field(min_length=1)
    sno: str = Field(min_length=1)
    title: str = Field(min_length=1)
    kind: EntryKind
    level: int = Field(ge=1, le=12)
    parent_entry_id: str | None = None
    parent_sno: str | None = None
    printed_start: PrintedPage
    physical_start: int | None = Field(default=None, ge=1)
    pdf_page_index: int | None = Field(default=None, ge=0)
    boundary: Boundary
    provenance: Provenance
    quality: Quality
    include: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def validate_coordinates_and_boundary(self) -> "OutlineContractEntry":
        if (self.physical_start is None) != (self.pdf_page_index is None):
            raise ValueError("physical_start and pdf_page_index must be supplied together")
        if self.physical_start is not None and self.pdf_page_index != self.physical_start - 1:
            raise ValueError("pdf_page_index must equal physical_start - 1")
        if self.include and self.boundary.allow_extraction and self.printed_start.numeric is None:
            raise ValueError("Extraction-enabled entries require a numeric printed page")
        if (
            self.provenance.analytical_or_verbatim == "analytical"
            and self.boundary.status == BoundaryStatus.PROPOSED
            and self.boundary.allow_extraction
        ):
            raise ValueError("Unverified analytical boundaries cannot be extraction-enabled")
        if self.boundary.status == BoundaryStatus.REJECTED and self.boundary.allow_extraction:
            raise ValueError("Rejected boundaries cannot be extraction-enabled")
        is_analytical = self.provenance.analytical_or_verbatim == "analytical"
        if is_analytical != (self.kind == EntryKind.ANALYTICAL_SECTION):
            raise ValueError("Analytical provenance and analytical_section kind must agree")
        return self


class DocumentMetadata(StrictModel):
    book_id: str = Field(min_length=1)
    pdf_filename: str = Field(min_length=1)
    pdf_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    title: str = Field(min_length=1)
    subtitle: str | None = None
    author: str | None = None
    total_pdf_pages: int = Field(ge=1)


class SourcePages(StrictModel):
    from_pdf_index: int = Field(ge=0)
    to_pdf_index: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "SourcePages":
        if self.to_pdf_index < self.from_pdf_index:
            raise ValueError("to_pdf_index must not precede from_pdf_index")
        return self


class GenerationMetadata(StrictModel):
    method: Literal[
        "human_curated", "deterministic_parser", "ollama_structured", "hybrid",
    ]
    generator: str = Field(min_length=1)
    model: str | None = None
    generated_at: str | None = None
    source_scope: str = Field(min_length=1)
    source_pages: SourcePages | None = None
    prompt_version: str | None = None


class PaginationMetadata(StrictModel):
    printed_to_physical_mapping_status: Literal["unresolved", "provisional", "verified"]
    default_offset: int | None = None
    mapping_sidecar: str | None = None


class ValidationState(StrictModel):
    status: Literal["not_validated", "valid", "invalid"]
    validated_at: str | None = None
    validator_version: str
    errors: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)


class ApprovalState(StrictModel):
    status: Literal["draft", "reviewed", "approved", "revoked"]
    approved_at: str | None = None
    approved_by: str | None = None
    outline_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class BookOutlineContract(StrictModel):
    schema_name: Literal["book_outline_contract"]
    schema_version: Literal["1.0.0"]
    document: DocumentMetadata
    generation: GenerationMetadata
    pagination: PaginationMetadata
    entries: list[OutlineContractEntry]
    validation: ValidationState
    approval: ApprovalState

    @model_validator(mode="after")
    def validate_outline(self) -> "BookOutlineContract":
        entry_ids = [entry.entry_id for entry in self.entries]
        snos = [entry.sno for entry in self.entries]
        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError("Duplicate entry_id values")
        if len(snos) != len(set(snos)):
            raise ValueError("Duplicate sno values")

        by_id = {entry.entry_id: entry for entry in self.entries}
        by_sno = {entry.sno: entry for entry in self.entries}
        for entry in self.entries:
            if (entry.parent_entry_id is None) != (entry.parent_sno is None):
                raise ValueError(f"Entry {entry.entry_id} must supply both parent references or neither")
            if entry.parent_entry_id is None:
                if entry.level != 1:
                    raise ValueError(f"Root entry {entry.entry_id} must have level 1")
                continue
            parent_by_id = by_id.get(entry.parent_entry_id)
            parent_by_sno = by_sno.get(entry.parent_sno or "")
            if parent_by_id is None:
                raise ValueError(f"Unknown parent_entry_id: {entry.parent_entry_id}")
            if parent_by_sno is None:
                raise ValueError(f"Unknown parent_sno: {entry.parent_sno}")
            if parent_by_id is not parent_by_sno:
                raise ValueError(f"Parent references disagree for {entry.entry_id}")
            if entry.level != parent_by_id.level + 1:
                raise ValueError(f"Level does not agree with parentage for {entry.entry_id}")
        return self


def contract_json_schema() -> dict:
    return BookOutlineContract.model_json_schema()
