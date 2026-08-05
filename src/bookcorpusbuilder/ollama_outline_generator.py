from __future__ import annotations

import json

from .outline_contract import BookOutlineContract


class OllamaUnavailableError(RuntimeError):
    pass


def generate_outline_with_ollama(
    source_text: str,
    model: str = "qwen3:8b",
    document_context: dict | None = None,
) -> BookOutlineContract:
    """Generate an unapproved candidate; never save, approve, map, or extract it."""
    try:
        from ollama import chat
    except ImportError as exc:
        raise OllamaUnavailableError(
            "Ollama support is optional. Install BOOKCORPUSBUILDER with the 'ollama' extra."
        ) from exc

    authoritative_document = json.dumps(document_context or {}, ensure_ascii=False, indent=2)
    prompt = f"""Create a candidate book outline from the supplied source.

Rules:
1. Return only data conforming to the supplied schema.
2. Never invent a printed page.
3. Use null when a physical or PDF coordinate is unknown.
4. Distinguish verbatim printed headings from analytical headings.
5. Analytical headings must use kind analytical_section, boundary.status proposed,
   boundary.allow_extraction false, and include false.
6. Do not approve the outline; approval.status must be draft.
7. validation.status must be not_validated.
8. Preserve source terminology.
9. Copy supplied authoritative document fields exactly; never invent or alter identity metadata.

AUTHORITATIVE DOCUMENT FIELDS:
{authoritative_document}

SOURCE:
{source_text}
"""
    response = chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        format=BookOutlineContract.model_json_schema(),
        options={"temperature": 0},
    )
    contract = BookOutlineContract.model_validate(json.loads(response.message.content))
    if contract.generation.method != "ollama_structured":
        raise ValueError("Ollama contract must declare generation.method = ollama_structured")
    if contract.approval.status != "draft" or contract.validation.status != "not_validated":
        raise ValueError("Ollama output must remain an unvalidated draft candidate")
    return contract
