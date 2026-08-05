from __future__ import annotations

from dataclasses import dataclass, field

from .outline_contract import BookOutlineContract, BoundaryStatus
from .outline_hashing import contract_payload_hash


VALIDATOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class ContractIssue:
    severity: str
    code: str
    message: str
    entry_id: str | None = None


@dataclass
class ContractValidationReport:
    issues: list[ContractIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ContractIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ContractIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def valid(self) -> bool:
        return not self.errors


def validate_contract_semantics(
    contract: BookOutlineContract,
    *,
    expected_book_id: str | None = None,
    expected_pdf_sha256: str | None = None,
    expected_pdf_pages: int | None = None,
) -> ContractValidationReport:
    report = ContractValidationReport()
    document = contract.document
    if expected_book_id and document.book_id != expected_book_id:
        report.issues.append(ContractIssue("error", "book_id_mismatch", "Contract book_id does not match the selected book."))
    if expected_pdf_sha256 and document.pdf_sha256 != expected_pdf_sha256:
        report.issues.append(ContractIssue("error", "pdf_hash_mismatch", "Contract PDF hash does not match the selected source PDF."))
    if expected_pdf_pages and document.total_pdf_pages != expected_pdf_pages:
        report.issues.append(ContractIssue("error", "pdf_page_count_mismatch", "Contract PDF page count does not match the selected source PDF."))
    source_pages = contract.generation.source_pages
    if source_pages and source_pages.to_pdf_index >= document.total_pdf_pages:
        report.issues.append(ContractIssue(
            "error", "source_scope_out_of_range",
            "Generation source_pages exceed the document PDF range.",
        ))

    for entry in contract.entries:
        provenance = entry.provenance
        if provenance.source_pdf_index is not None and provenance.source_pdf_index >= document.total_pdf_pages:
            report.issues.append(ContractIssue(
                "error", "source_evidence_out_of_range",
                "Provenance source_pdf_index exceeds the document PDF range.", entry.entry_id,
            ))
        if provenance.analytical_or_verbatim == "verbatim" and not provenance.raw_source_text:
            report.issues.append(ContractIssue(
                "error", "missing_verbatim_evidence",
                "Verbatim entries require raw_source_text evidence.", entry.entry_id,
            ))
        if (
            provenance.source_page_label
            and entry.printed_start.label
            and provenance.source_page_label != entry.printed_start.label
        ):
            report.issues.append(ContractIssue(
                "warning", "source_page_label_mismatch",
                "Provenance page label differs from printed_start.label.", entry.entry_id,
            ))
        if entry.provenance.analytical_or_verbatim == "analytical":
            if entry.boundary.status == BoundaryStatus.PROPOSED:
                report.issues.append(ContractIssue(
                    "warning", "boundary_requires_review",
                    "Analytical boundary requires physical-page verification before extraction.",
                    entry.entry_id,
                ))
            if entry.include and not entry.boundary.allow_extraction:
                report.issues.append(ContractIssue(
                    "warning", "analytical_metadata_only",
                    "Included analytical metadata is not an extraction boundary.",
                    entry.entry_id,
                ))
        if entry.physical_start is not None and entry.physical_start > document.total_pdf_pages:
            report.issues.append(ContractIssue(
                "error", "physical_page_out_of_range",
                "Entry physical_start exceeds document.total_pdf_pages.", entry.entry_id,
            ))

    if contract.approval.status == "approved":
        expected_hash = contract_payload_hash(contract)
        if contract.approval.outline_sha256 != expected_hash:
            report.issues.append(ContractIssue("error", "approval_hash_mismatch", "Approved contract hash does not match its payload."))
        if contract.validation.status != "valid":
            report.issues.append(ContractIssue("error", "approved_without_validation", "Approved contracts must have validation.status = valid."))
        if contract.pagination.printed_to_physical_mapping_status != "verified":
            report.issues.append(ContractIssue("error", "approved_without_mapping", "Approved contracts must have verified pagination."))
    return report


def lifecycle_state(contract: BookOutlineContract, report: ContractValidationReport) -> str:
    if contract.approval.status == "approved" and report.valid:
        return "extraction_ready"
    if contract.pagination.printed_to_physical_mapping_status == "verified":
        return "page_mapped"
    if contract.approval.status == "reviewed":
        return "human_reviewed"
    if contract.validation.status == "valid" and report.valid:
        return "source_checked" if not report.warnings else "schema_valid"
    return "generated_candidate"
