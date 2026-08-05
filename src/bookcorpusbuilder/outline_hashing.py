from __future__ import annotations

import hashlib
import json

from .outline_contract import BookOutlineContract


def contract_payload_hash(contract: BookOutlineContract) -> str:
    """Hash contract content while excluding its self-referential approval hash."""
    payload = contract.model_dump(mode="json")
    payload["approval"] = {**payload["approval"], "outline_sha256": None}
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
