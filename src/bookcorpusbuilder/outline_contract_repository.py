from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .outline_contract import BookOutlineContract
from .outline_validation import lifecycle_state, validate_contract_semantics


STAGE_FILENAMES = {
    "candidate": "outline_candidate.json",
    "reviewed": "outline_reviewed.json",
    "approved": "outline_approved.json",
}


class OutlineContractRepository:
    """Atomic versioned-contract storage, separate from legacy CSV compatibility files."""

    def __init__(self, outline_root: Path):
        self.outline_root = outline_root

    def path(self, book_id: str, stage: str) -> Path:
        if stage not in STAGE_FILENAMES:
            raise ValueError(f"Unknown outline contract stage: {stage}")
        return self.outline_root / book_id / STAGE_FILENAMES[stage]

    def save(self, contract: BookOutlineContract, stage: str) -> Path:
        report = validate_contract_semantics(contract)
        if stage == "reviewed" and (
            contract.approval.status not in {"reviewed", "approved"}
            or contract.validation.status != "valid"
            or not report.valid
        ):
            raise ValueError(
                "Reviewed contract storage requires valid deterministic checks and approval.status reviewed or approved"
            )
        if stage == "approved" and lifecycle_state(contract, report) != "extraction_ready":
            raise ValueError("Approved contract storage requires a valid, mapped, hash-bound contract")
        target = self.path(contract.document.book_id, stage)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = contract.model_dump(mode="json")
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temporary, target)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise
        return target

    def load(self, book_id: str, stage: str) -> BookOutlineContract | None:
        path = self.path(book_id, stage)
        if not path.exists():
            return None
        return BookOutlineContract.model_validate_json(path.read_text(encoding="utf-8"))
