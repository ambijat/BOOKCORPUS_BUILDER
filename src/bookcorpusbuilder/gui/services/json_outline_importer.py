from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field

from pydantic import ValidationError

from ...outline_contract import BookOutlineContract, NumberingSystem
from ...outline_validation import lifecycle_state, validate_contract_semantics
from ..models import OutlineCandidate
from .common import sha256_bytes


ACCEPTED_KINDS = {
    "part", "chapter", "section", "subsection", "analytical_section",
    "preface", "introduction", "appendix", "bibliography", "notes",
    "index", "caption", "topic", "glossary", "acknowledgement", "other",
}
ROW_KEYS = {
    "sno", "title", "kind", "printed_start", "physical_start", "pdf_index",
    "level", "parent_sno", "source", "include", "children",
}
TOP_LEVEL_KEYS = {"book", "outline"}
BOOK_KEYS = {"title", "author"}
ROMAN_LABEL = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)


class JsonOutlineImportError(ValueError):
    """Raised when JSON cannot be decoded or has no supported outline root."""


@dataclass(frozen=True)
class JsonImportDiagnostic:
    code: str
    message: str
    path: str = "$"
    severity: str = "warning"


@dataclass
class JsonOutlineImportResult:
    candidates: list[OutlineCandidate] = field(default_factory=list)
    diagnostics: list[JsonImportDiagnostic] = field(default_factory=list)
    import_hash: str = ""
    book_metadata: dict = field(default_factory=dict)
    contract: BookOutlineContract | None = None
    lifecycle_state: str = ""

    @property
    def error_count(self) -> int:
        return sum(item.severity == "error" for item in self.diagnostics)


class JsonOutlineImporter:
    """Import supported JSON outline documents without heuristic text parsing."""

    def import_text(
        self,
        text: str,
        *,
        expected_book_id: str | None = None,
        expected_pdf_sha256: str | None = None,
        expected_pdf_pages: int | None = None,
    ) -> JsonOutlineImportResult:
        raw = text.encode("utf-8")
        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            raise JsonOutlineImportError(
                f"Malformed JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc

        result = JsonOutlineImportResult(import_hash=sha256_bytes(raw))
        if isinstance(document, dict) and document.get("schema_name") == "book_outline_contract":
            return self._import_contract(
                document, result,
                expected_book_id=expected_book_id,
                expected_pdf_sha256=expected_pdf_sha256,
                expected_pdf_pages=expected_pdf_pages,
            )
        if isinstance(document, list):
            outline = document
        elif isinstance(document, dict):
            unknown_top = sorted(set(document) - TOP_LEVEL_KEYS)
            for key in unknown_top:
                result.diagnostics.append(JsonImportDiagnostic(
                    "unknown_key", f"Unknown document key '{key}' was ignored.", f"$.{key}"
                ))
            outline = document.get("outline")
            book = document.get("book", {})
            if book is None:
                book = {}
            if not isinstance(book, dict):
                result.diagnostics.append(JsonImportDiagnostic(
                    "invalid_book_metadata", "The 'book' value must be an object.", "$.book", "error"
                ))
                book = {}
            for key in sorted(set(book) - BOOK_KEYS):
                result.diagnostics.append(JsonImportDiagnostic(
                    "unknown_key", f"Unknown book key '{key}' was retained only in diagnostics.",
                    f"$.book.{key}",
                ))
            result.book_metadata = {key: book[key] for key in BOOK_KEYS if key in book}
        else:
            raise JsonOutlineImportError("JSON outline must be a list or an object containing an 'outline' list.")

        if not isinstance(outline, list):
            raise JsonOutlineImportError("JSON document must contain an 'outline' list.")

        flattened: list[tuple[dict, str, str, int]] = []
        self._flatten(outline, flattened, result.diagnostics, "$.outline" if isinstance(document, dict) else "$", "", 1)
        source_snos = [self._text(row.get("sno")) for row, _path, _parent, _depth in flattened]
        counts = Counter(value for value in source_snos if value)
        existing = set(value for value in source_snos if value)

        for position, (row, path, inherited_parent, depth) in enumerate(flattened, 1):
            candidate = self._candidate(
                row, path, inherited_parent, depth, position, counts, existing,
                result.import_hash, result.diagnostics,
            )
            result.candidates.append(candidate)

        by_source_sno = {
            candidate.source_sno: candidate
            for candidate in result.candidates
            if candidate.source_sno
        }
        for candidate in result.candidates:
            parent = by_source_sno.get(candidate.parent_sno)
            candidate.parent_candidate_id = parent.candidate_id if parent else None
        return result

    def _import_contract(
        self,
        document: dict,
        result: JsonOutlineImportResult,
        *,
        expected_book_id: str | None,
        expected_pdf_sha256: str | None,
        expected_pdf_pages: int | None,
    ) -> JsonOutlineImportResult:
        try:
            contract = BookOutlineContract.model_validate(document)
        except ValidationError as exc:
            details = []
            for error in exc.errors(include_url=False):
                path = "$" + "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error["loc"]
                )
                details.append(f"{path}: {error['msg']}")
            raise JsonOutlineImportError(
                "JSON does not conform to book_outline_contract v1: " + "; ".join(details[:12])
            ) from exc

        result.contract = contract
        result.book_metadata = contract.document.model_dump(mode="json")
        report = validate_contract_semantics(
            contract,
            expected_book_id=expected_book_id,
            expected_pdf_sha256=expected_pdf_sha256,
            expected_pdf_pages=expected_pdf_pages,
        )
        result.lifecycle_state = lifecycle_state(contract, report)
        for issue in report.issues:
            path = f"$.entries[{issue.entry_id}]" if issue.entry_id else "$"
            result.diagnostics.append(JsonImportDiagnostic(
                issue.code, issue.message, path, issue.severity,
            ))

        entry_errors = {
            issue.entry_id for issue in report.errors if issue.entry_id is not None
        }
        global_error = any(issue.entry_id is None for issue in report.errors)
        for position, entry in enumerate(contract.entries, 1):
            warning_codes = list(entry.quality.warning_codes)
            warning_codes.extend(
                issue.code for issue in report.issues
                if issue.entry_id == entry.entry_id and issue.code not in warning_codes
            )
            printed = entry.printed_start
            if printed.numeric is None:
                code = (
                    "roman_page"
                    if printed.numbering_system in {NumberingSystem.ROMAN_LOWER, NumberingSystem.ROMAN_UPPER}
                    else "missing_printed_page"
                )
                if code not in warning_codes:
                    warning_codes.append(code)
            if not entry.boundary.allow_extraction and "metadata_only_boundary" not in warning_codes:
                warning_codes.append("metadata_only_boundary")

            source = entry.provenance.source_type
            candidate = OutlineCandidate(
                raw_text=json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                sno=position,
                title=entry.title,
                kind=entry.kind.value,
                printed_page=printed.numeric,
                printed_page_label=printed.label or "",
                physical_start=entry.physical_start,
                pdf_page_index=entry.pdf_page_index,
                level=entry.level,
                source=source,
                confidence=entry.quality.confidence,
                include=(
                    entry.include and entry.boundary.allow_extraction
                    and entry.entry_id not in entry_errors and not global_error
                ),
                warning_codes=warning_codes,
                parser_rule="book_outline_contract_v1",
                sno_explicit=True,
                source_sno=entry.sno,
                parent_sno=entry.parent_sno or "",
                raw_import_hash=result.import_hash,
                entry_id=entry.entry_id,
                parent_entry_id=entry.parent_entry_id or "",
                provenance_source_type=entry.provenance.source_type,
                analytical_or_verbatim=entry.provenance.analytical_or_verbatim,
                boundary_status=entry.boundary.status.value,
                boundary_basis=entry.boundary.basis,
                allow_extraction=entry.boundary.allow_extraction,
                notes=entry.notes or "",
            )
            result.candidates.append(candidate)

        by_entry_id = {
            candidate.entry_id: candidate for candidate in result.candidates if candidate.entry_id
        }
        for candidate in result.candidates:
            parent = by_entry_id.get(candidate.parent_entry_id)
            candidate.parent_candidate_id = parent.candidate_id if parent else None
        return result

    def _flatten(
        self,
        rows: list,
        flattened: list[tuple[dict, str, str, int]],
        diagnostics: list[JsonImportDiagnostic],
        base_path: str,
        inherited_parent: str,
        depth: int,
    ) -> None:
        for index, value in enumerate(rows):
            path = f"{base_path}[{index}]"
            if not isinstance(value, dict):
                diagnostics.append(JsonImportDiagnostic(
                    "row_not_object", "Outline rows must be JSON objects.", path, "error"
                ))
                continue
            for key in sorted(set(value) - ROW_KEYS):
                diagnostics.append(JsonImportDiagnostic(
                    "unknown_key", f"Unknown row key '{key}' was ignored.", f"{path}.{key}"
                ))
            flattened.append((value, path, inherited_parent, depth))
            children = value.get("children", [])
            if children is None:
                children = []
            if not isinstance(children, list):
                diagnostics.append(JsonImportDiagnostic(
                    "invalid_children", "The 'children' value must be a list.",
                    f"{path}.children", "error",
                ))
                continue
            parent = self._text(value.get("sno")) or inherited_parent
            self._flatten(children, flattened, diagnostics, f"{path}.children", parent, depth + 1)

    def _candidate(
        self,
        row: dict,
        path: str,
        inherited_parent: str,
        depth: int,
        position: int,
        counts: Counter,
        existing: set[str],
        import_hash: str,
        diagnostics: list[JsonImportDiagnostic],
    ) -> OutlineCandidate:
        warning_codes: list[str] = []
        source_sno = self._text(row.get("sno"))
        if not source_sno:
            self._error(diagnostics, warning_codes, "missing_sno", "sno must be non-empty.", f"{path}.sno")
        elif counts[source_sno] > 1:
            self._error(diagnostics, warning_codes, "duplicate_sno", f"sno '{source_sno}' is duplicated.", f"{path}.sno")

        title_value = row.get("title")
        title = title_value.strip() if isinstance(title_value, str) else ""
        if not title:
            self._error(diagnostics, warning_codes, "missing_title", "title must be non-empty.", f"{path}.title")

        kind_value = row.get("kind")
        kind = kind_value.strip().casefold() if isinstance(kind_value, str) else ""
        if kind not in ACCEPTED_KINDS:
            self._error(
                diagnostics, warning_codes, "invalid_kind",
                f"kind must be one of: {', '.join(sorted(ACCEPTED_KINDS))}.", f"{path}.kind",
            )
            kind = kind or "other"

        printed_value = row.get("printed_start")
        printed_page: int | None = None
        printed_label = ""
        if printed_value is None:
            warning_codes.append("missing_printed_page")
            diagnostics.append(JsonImportDiagnostic(
                "missing_printed_page",
                "printed_start is null; the row is retained as metadata but excluded from extraction boundaries.",
                f"{path}.printed_start",
            ))
        elif isinstance(printed_value, int) and not isinstance(printed_value, bool):
            printed_page = printed_value
            printed_label = str(printed_value)
        elif isinstance(printed_value, str) and ROMAN_LABEL.fullmatch(printed_value.strip()):
            printed_label = printed_value.strip().lower()
            warning_codes.append("roman_page")
        else:
            self._error(
                diagnostics, warning_codes, "invalid_printed_page",
                "printed_start must be an integer, Roman label, or null.", f"{path}.printed_start",
            )

        physical_value = row.get("physical_start")
        physical_start: int | None = None
        if physical_value is not None:
            if isinstance(physical_value, int) and not isinstance(physical_value, bool) and physical_value >= 1:
                physical_start = physical_value
            else:
                self._error(
                    diagnostics, warning_codes, "invalid_physical_start",
                    "physical_start must be a positive integer or null.", f"{path}.physical_start",
                )

        pdf_index_value = row.get("pdf_index")
        pdf_page_index: int | None = None
        if pdf_index_value is not None:
            if isinstance(pdf_index_value, int) and not isinstance(pdf_index_value, bool) and pdf_index_value >= 0:
                pdf_page_index = pdf_index_value
            else:
                self._error(
                    diagnostics, warning_codes, "invalid_pdf_index",
                    "pdf_index must be a non-negative integer or null.", f"{path}.pdf_index",
                )

        if physical_start is not None and pdf_page_index is not None and pdf_page_index != physical_start - 1:
            self._error(
                diagnostics, warning_codes, "pdf_index_mismatch",
                "pdf_index must equal physical_start - 1.", f"{path}.pdf_index",
            )

        level_value = row.get("level")
        if isinstance(level_value, int) and not isinstance(level_value, bool) and level_value > 0:
            level = level_value
        else:
            level = depth
            self._error(
                diagnostics, warning_codes, "invalid_level",
                "level must be a positive integer.", f"{path}.level",
            )

        explicit_parent = row.get("parent_sno")
        parent_sno = self._text(explicit_parent) if explicit_parent is not None else inherited_parent
        if parent_sno and parent_sno not in existing:
            self._error(
                diagnostics, warning_codes, "orphan_parent",
                f"parent_sno '{parent_sno}' does not reference an imported sno.", f"{path}.parent_sno",
            )

        include_value = row.get("include", True)
        if isinstance(include_value, bool):
            include = include_value
        else:
            include = False
            self._error(
                diagnostics, warning_codes, "invalid_include",
                "include must be Boolean.", f"{path}.include",
            )
        if printed_value is None:
            include = False

        source_value = row.get("source", "imported_json")
        source = source_value.strip() if isinstance(source_value, str) and source_value.strip() else "imported_json"
        if "source" in row and source == "imported_json" and source_value != "imported_json":
            diagnostics.append(JsonImportDiagnostic(
                "invalid_source", "source must be a non-empty string; imported_json was used.",
                f"{path}.source", "error",
            ))
            warning_codes.append("invalid_source")
            include = False

        blocking = any(code in warning_codes for code in {
            "missing_sno", "duplicate_sno", "missing_title", "invalid_kind",
            "invalid_printed_page", "invalid_level", "orphan_parent", "invalid_include",
            "invalid_source", "invalid_physical_start", "invalid_pdf_index", "pdf_index_mismatch",
        })
        internal_sno = int(source_sno) if source_sno.isdigit() and int(source_sno) > 0 else position
        return OutlineCandidate(
            raw_text=json.dumps(row, ensure_ascii=False, sort_keys=True),
            sno=internal_sno,
            title=title,
            kind=kind,
            printed_page=printed_page,
            printed_page_label=printed_label,
            physical_start=physical_start,
            pdf_page_index=pdf_page_index,
            level=level,
            source=source,
            confidence=1.0 if not warning_codes else 0.8,
            include=include and not blocking,
            warning_codes=warning_codes,
            parser_rule="json_import",
            sno_explicit=True,
            source_sno=source_sno,
            parent_sno=parent_sno,
            raw_import_hash=import_hash,
        )

    @staticmethod
    def _text(value) -> str:
        return "" if value is None else str(value).strip()

    @staticmethod
    def _error(
        diagnostics: list[JsonImportDiagnostic],
        warnings: list[str],
        code: str,
        message: str,
        path: str,
    ) -> None:
        warnings.append(code)
        diagnostics.append(JsonImportDiagnostic(code, message, path, "error"))
