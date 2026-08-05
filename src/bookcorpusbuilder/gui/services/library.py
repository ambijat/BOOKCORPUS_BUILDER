from __future__ import annotations

import shutil
from pathlib import Path

from ..models import BookRecord
from .common import atomic_write_json, read_json, sha256_file, stable_book_id, utc_now


class DuplicateBookError(ValueError):
    def __init__(self, record: BookRecord):
        super().__init__(f"This PDF is already registered as {record.filename}")
        self.record = record


class LibraryImportError(RuntimeError):
    """A PDF import failed at an identifiable stage.

    ``stage`` and ``source`` let callers build an operator-facing message
    without re-deriving where in the import pipeline things went wrong.
    """

    def __init__(self, stage: str, source: Path, original: Exception):
        self.stage = stage
        self.source = source
        self.original = original
        super().__init__(f"{stage} failed: {original}")


class LibraryService:
    def __init__(self, input_dir: Path, registry_path: Path):
        self.input_dir = input_dir
        self.registry_path = registry_path
        self.input_dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        return read_json(self.registry_path, {"books": {}, "hidden": []})

    def _save(self, value: dict) -> None:
        atomic_write_json(self.registry_path, value)

    def _inspect_pdf(self, path: Path) -> tuple[int, str]:
        try:
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                count = len(pdf.pages)
                samples = [pdf.pages[i].extract_text() or "" for i in range(min(3, count))]
            chars = sum(len(item.strip()) for item in samples)
            return count, "text-extractable" if chars >= 80 else "likely-scanned"
        except Exception:
            return 0, "unreadable-or-dependency-missing"

    def books(self, inspect: bool = False) -> list[BookRecord]:
        state = self._load()
        hidden = set(state.get("hidden", []))
        changed = False
        for pdf in sorted(self.input_dir.glob("*.pdf")):
            digest = sha256_file(pdf)
            book_id = stable_book_id(digest)
            if book_id not in state["books"]:
                pages, text_status = self._inspect_pdf(pdf) if inspect else (0, "unknown")
                state["books"][book_id] = BookRecord(
                    book_id=book_id, filename=pdf.name, pdf_path=str(pdf.resolve()),
                    source_hash=digest, size_bytes=pdf.stat().st_size,
                    page_count=pages, text_status=text_status, registered_at=utc_now(),
                ).__dict__
                changed = True
            elif inspect:
                pages, text_status = self._inspect_pdf(pdf)
                state["books"][book_id].update({
                    "pdf_path": str(pdf.resolve()), "size_bytes": pdf.stat().st_size,
                    "page_count": pages, "text_status": text_status,
                })
                changed = True
        if changed:
            self._save(state)
        return [BookRecord(**value) for key, value in state["books"].items() if key not in hidden]

    def add(self, source: Path) -> BookRecord:
        """Import ``source`` into the library.

        Registration never depends on whether the PDF's text is extractable
        (see ``_inspect_pdf``, which always degrades gracefully). A book
        that was previously imported and then hidden via
        ``remove_registration`` is restored rather than rejected as a
        duplicate -- that hidden state is otherwise invisible and
        unreachable from the UI, so treating a re-add as a no-op duplicate
        would silently strand the operator with no way back in.
        """
        stage = "validating source"
        temporary: Path | None = None
        try:
            if source.suffix.lower() != ".pdf" or not source.is_file():
                raise ValueError(f"Not a readable PDF file: {source}")

            stage = "hashing source"
            digest = sha256_file(source)
            book_id = stable_book_id(digest)

            stage = "checking for duplicates"
            state = self._load()
            hidden_before = set(state.get("hidden", []))
            previous_entry = state["books"].get(book_id)
            if previous_entry is not None and book_id not in hidden_before:
                raise DuplicateBookError(BookRecord(**previous_entry))

            destination = self.input_dir / source.name
            if destination.exists() and sha256_file(destination) != digest:
                destination = self.input_dir / f"{book_id}__{source.name}"
            temporary = destination.with_name(f".{destination.name}.importing")

            stage = "copying into library"
            try:
                shutil.copy2(source, temporary)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise

            stage = "inspecting PDF"
            pages, text_status = self._inspect_pdf(temporary)

            stage = "building record"
            record = BookRecord(
                book_id=book_id, filename=source.name, pdf_path=str(destination.resolve()),
                source_hash=digest, size_bytes=temporary.stat().st_size,
                page_count=pages, text_status=text_status,
                original_source=str(source.resolve()), registered_at=utc_now(),
            )

            stage = "saving registry"
            state["books"][book_id] = record.__dict__
            state["hidden"] = [value for value in state.get("hidden", []) if value != book_id]
            try:
                self._save(state)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise

            stage = "finalizing import"
            try:
                temporary.replace(destination)
            except Exception:
                self._restore_previous_entry(book_id, previous_entry, was_hidden=book_id in hidden_before)
                temporary.unlink(missing_ok=True)
                raise

            return record
        except DuplicateBookError:
            raise
        except Exception as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise LibraryImportError(stage, source, exc) from exc

    def _restore_previous_entry(self, book_id: str, previous_entry: dict | None, was_hidden: bool) -> None:
        """Undo a registry write for ``book_id`` after a later import step failed."""
        state = self._load()
        if previous_entry is None:
            state["books"].pop(book_id, None)
        else:
            state["books"][book_id] = previous_entry
        hidden = [value for value in state.get("hidden", []) if value != book_id]
        if was_hidden:
            hidden.append(book_id)
        state["hidden"] = sorted(set(hidden))
        self._save(state)

    def remove_registration(self, book_id: str) -> None:
        state = self._load()
        if book_id not in state["books"]:
            raise KeyError(book_id)
        state.setdefault("hidden", []).append(book_id)
        state["hidden"] = sorted(set(state["hidden"]))
        self._save(state)

    def get(self, book_id: str) -> BookRecord:
        state = self._load()
        return BookRecord(**state["books"][book_id])
