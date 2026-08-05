from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from io import StringIO

from ..models import MergeAnalysis, MergeItem, OutlineCandidate, OutlineEntry


ROMAN_PAGE = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)
ARABIC_PAGE = re.compile(r"^\d{1,6}$")
TRAILING_PAGE = re.compile(
    r"^(?P<title>.+?)\s*(?P<separator>\.{2,}|…+|·{2,}|_{2,}|\s{2,}|\s)\s*"
    r"(?P<page>\d{1,6}|[ivxlcdm]+)\s*$",
    re.IGNORECASE,
)
STRUCTURAL = re.compile(
    r"^(?P<kind>part|chapter)\s+(?P<number>\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"(?:[.():\-–—]\s*|\s+)?(?P<rest>.*)$",
    re.IGNORECASE,
)
NUMERIC_HEADING = re.compile(r"^(?P<number>\d+(?:\.\d+)*)(?:[.)])?\s+(?P<rest>.+)$")
TOC_HEADER = re.compile(r"^(?:table\s+of\s+)?contents?(?:\s+continued)?$", re.IGNORECASE)


@dataclass
class OutlineParseResult:
    candidates: list[OutlineCandidate] = field(default_factory=list)

    @property
    def usable_count(self) -> int:
        return sum(1 for item in self.candidates if item.include and item.title)


def normalise_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()


def _page_value(label: str) -> tuple[int | None, str, list[str]]:
    label = label.strip()
    if ARABIC_PAGE.fullmatch(label):
        return int(label), label, []
    if ROMAN_PAGE.fullmatch(label):
        return None, label.lower(), ["roman_page"]
    return None, label, ["ambiguous_page"]


def _structure(title: str) -> tuple[str, int, bool]:
    structural = STRUCTURAL.match(title.strip())
    if structural:
        return structural.group("kind").casefold(), 1 if structural.group("kind").casefold() == "part" else 2, True
    numeric = NUMERIC_HEADING.match(title.strip())
    if numeric:
        return "section", numeric.group("number").count(".") + 1, True
    lowered = title.strip().casefold()
    for label, kind in (("appendix", "appendix"), ("bibliography", "bibliography"), ("references", "bibliography"), ("notes", "notes"), ("index", "index")):
        if lowered.startswith(label):
            return kind, 1, False
    return "section", 1, False


def _delimited(line: str) -> tuple[str | None, str, str] | None:
    delimiter = "\t" if "\t" in line else "|" if "|" in line else "," if "," in line else ""
    if not delimiter:
        return None
    try:
        fields = next(csv.reader(StringIO(line), delimiter=delimiter))
    except (csv.Error, StopIteration):
        return None
    fields = [field.strip() for field in fields]
    if len(fields) == 2 and fields[0] and (ARABIC_PAGE.fullmatch(fields[1]) or ROMAN_PAGE.fullmatch(fields[1])):
        return None, fields[0], fields[1]
    source_sno = fields[0] if fields and re.fullmatch(r"\d+(?:\.\d+)*", fields[0]) else None
    if len(fields) >= 3 and source_sno and fields[1] and (ARABIC_PAGE.fullmatch(fields[-1]) or ROMAN_PAGE.fullmatch(fields[-1])):
        return source_sno, " ".join(fields[1:-1]).strip(), fields[-1]
    return None


class OutlineTextParser:
    """Deterministic, Qt-independent parser for pasted outline text."""

    def parse(self, text: str, source: str = "pasted_outline") -> OutlineParseResult:
        candidates: list[OutlineCandidate] = []
        pending: list[str] = []
        pending_kind = ""
        pending_level = 1

        def append_candidate(
            raw_text: str,
            title: str,
            page_label: str = "",
            rule: str = "ambiguous",
            confidence: float = 0.4,
            sno: int | None = None,
            sno_explicit: bool = False,
            forced_kind: str = "",
            forced_level: int | None = None,
            source_sno: str = "",
        ) -> None:
            clean_title = re.sub(r"\s+", " ", title).strip(" .…·_|\t")
            kind, level, _ = _structure(clean_title)
            page, printed_label, warnings = _page_value(page_label) if page_label else (None, "", ["missing_page"])
            if not clean_title:
                warnings.append("missing_title")
            candidates.append(OutlineCandidate(
                raw_text=raw_text,
                sno=sno,
                title=clean_title,
                kind=forced_kind or kind,
                printed_page=page,
                printed_page_label=printed_label,
                level=forced_level or level,
                source=source,
                confidence=confidence,
                include=bool(clean_title),
                warning_codes=warnings,
                parser_rule=rule,
                sno_explicit=sno_explicit,
                source_sno=source_sno,
            ))

        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        repeated = Counter(line.strip().casefold() for line in lines if line.strip())
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if TOC_HEADER.fullmatch(line):
                append_candidate(raw, line, rule="running_header", confidence=0.15)
                candidates[-1].include = False
                candidates[-1].warning_codes = ["possible_running_header", "possible_noise"]
                continue
            if repeated[line.casefold()] > 1 and not TRAILING_PAGE.match(line) and _delimited(line) is None:
                append_candidate(raw, line, rule="repeated_noise", confidence=0.12)
                candidates[-1].include = False
                candidates[-1].warning_codes = ["possible_running_header", "possible_noise", "ambiguous_page"]
                continue

            delimited = _delimited(line)
            if delimited:
                source_sno, title, page_label = delimited
                sno = int(source_sno) if source_sno and source_sno.isdigit() else None
                level = source_sno.count(".") + 1 if source_sno else None
                append_candidate(
                    raw, title, page_label, "delimited", 0.96, sno,
                    source_sno is not None, forced_level=level, source_sno=source_sno or "",
                )
                continue

            if (ARABIC_PAGE.fullmatch(line) or ROMAN_PAGE.fullmatch(line)) and pending:
                append_candidate("\n".join([*pending, raw]), " ".join(pending), line, "multiline", 0.72, forced_kind=pending_kind, forced_level=pending_level)
                pending.clear()
                pending_kind = ""
                pending_level = 1
                continue

            trailing = TRAILING_PAGE.match(line)
            if trailing:
                title_part = trailing.group("title").strip(" .…·_")
                separator = trailing.group("separator")
                # "Chapter 1" is a structural label, not a title whose page is 1.
                structural = STRUCTURAL.match(line)
                if structural and not structural.group("rest") and not re.search(r"\.{2,}|…|·{2,}|_|\t|\s{2,}", raw):
                    pending.append(line)
                    pending_kind = structural.group("kind").casefold()
                    pending_level = 1 if pending_kind == "part" else 2
                    continue
                combined = " ".join([*pending, title_part])
                rule = "dotted_leader" if re.search(r"\.{2,}|…|·{2,}|_", separator) else "plain_title_page"
                confidence = 0.93 if rule == "dotted_leader" else 0.82
                append_candidate(
                    "\n".join([*pending, raw]), combined, trailing.group("page"), rule, confidence,
                    forced_kind=pending_kind, forced_level=pending_level if pending_kind else None,
                )
                pending.clear()
                pending_kind = ""
                pending_level = 1
                continue

            structural = STRUCTURAL.match(line)
            if structural:
                kind = structural.group("kind").casefold()
                level = 1 if kind == "part" else 2
                if structural.group("rest").strip():
                    if pending:
                        append_candidate("\n".join(pending), " ".join(pending), rule="ambiguous_multiline", confidence=0.35, forced_kind=pending_kind, forced_level=pending_level)
                        candidates[-1].warning_codes.append("ambiguous_page")
                        pending.clear()
                    append_candidate(raw, line, rule="structural_without_page", confidence=0.68, forced_kind=kind, forced_level=level)
                else:
                    pending.append(line)
                    pending_kind = kind
                    pending_level = level
                continue

            if pending and len(pending) >= 3:
                append_candidate("\n".join(pending), " ".join(pending), rule="ambiguous_multiline", confidence=0.3, forced_kind=pending_kind, forced_level=pending_level)
                candidates[-1].warning_codes.append("ambiguous_page")
                pending.clear()
                pending_kind = ""
                pending_level = 1
            pending.append(line)

        if pending:
            append_candidate("\n".join(pending), " ".join(pending), rule="ambiguous_multiline", confidence=0.3, forced_kind=pending_kind, forced_level=pending_level)
            candidates[-1].warning_codes.append("ambiguous_page")

        self._finish(candidates)
        return OutlineParseResult(candidates)

    def _finish(self, candidates: list[OutlineCandidate]) -> None:
        # Hierarchical source identifiers such as 2.14 are provenance, not
        # integer canonical serial numbers. Keep them separately and assign a
        # stable sequential integer Sno so mixed top-level/child rows cannot
        # collide (for example canonical 2 versus the second row, source 1.1).
        if any("." in candidate.source_sno for candidate in candidates):
            for position, candidate in enumerate(candidates, 1):
                if candidate.source_sno:
                    candidate.sno = position

        active_part = False
        for candidate in candidates:
            if candidate.kind == "part":
                active_part = True
            elif candidate.kind == "chapter":
                candidate.level = 2 if active_part else 1

        # A part without a page inherits its first child's printed page as a
        # transparent, reviewable inference rather than being silently dropped.
        for index, candidate in enumerate(candidates):
            if candidate.kind != "part" or candidate.printed_page is not None or candidate.printed_page_label:
                continue
            for following in candidates[index + 1:]:
                if following.level <= candidate.level:
                    break
                if following.printed_page is not None:
                    candidate.printed_page = following.printed_page
                    candidate.printed_page_label = str(following.printed_page)
                    candidate.warning_codes = [code for code in candidate.warning_codes if code != "missing_page"]
                    candidate.warning_codes.append("page_inferred_from_child")
                    candidate.confidence = min(candidate.confidence, 0.62)
                    break

        stack: list[OutlineCandidate] = []
        for position, candidate in enumerate(candidates, 1):
            if candidate.sno is None:
                candidate.sno = position
            while stack and stack[-1].level >= candidate.level:
                stack.pop()
            candidate.parent_candidate_id = stack[-1].candidate_id if stack else None
            candidate.parent_sno = stack[-1].source_sno if stack else ""
            if candidate.level > 1 and candidate.parent_candidate_id is None:
                candidate.warning_codes.append("unresolved_hierarchy")
            stack.append(candidate)

        title_groups: dict[str, list[OutlineCandidate]] = {}
        sno_groups: dict[int, list[OutlineCandidate]] = {}
        for candidate in candidates:
            title_groups.setdefault(normalise_title(candidate.title), []).append(candidate)
            if candidate.sno is not None:
                sno_groups.setdefault(candidate.sno, []).append(candidate)
        for group in title_groups.values():
            if group[0].title and len(group) > 1:
                for candidate in group:
                    candidate.warning_codes.append("duplicate_title")
        for group in sno_groups.values():
            if len(group) > 1:
                for candidate in group:
                    candidate.warning_codes.append("duplicate_sno")


class OutlineMergeService:
    def analyse(self, draft: list[OutlineEntry], candidates: list[OutlineCandidate]) -> MergeAnalysis:
        result = MergeAnalysis()
        for candidate in candidates:
            if not candidate.include:
                result.ignored_rows.append(MergeItem("ignored", candidate, reason="Candidate excluded"))
                continue
            normalised = normalise_title(candidate.title)
            exact = next((entry for entry in draft if normalise_title(entry.title) == normalised), None)
            if exact:
                same_page = (
                    exact.printed_start == candidate.printed_page
                    if exact.printed_start is not None or candidate.printed_page is not None
                    else (exact.printed_page_label or "").casefold() == candidate.printed_page_label.casefold()
                )
                if same_page and exact.kind == candidate.kind and exact.level == candidate.level:
                    result.matching_rows.append(MergeItem("match", candidate, exact, "Same title, page, kind, and level"))
                else:
                    result.conflicting_rows.append(MergeItem("conflict", candidate, exact, "Same title with different page or structure"))
                continue
            same_page = next((entry for entry in draft if candidate.printed_page is not None and entry.printed_start == candidate.printed_page), None)
            if same_page:
                result.conflicting_rows.append(MergeItem("conflict", candidate, same_page, "Same printed page with a different title"))
                continue
            near = next((entry for entry in draft if SequenceMatcher(None, normalised, normalise_title(entry.title)).ratio() >= 0.9), None)
            if near:
                result.conflicting_rows.append(MergeItem("conflict", candidate, near, "Near-duplicate title"))
                continue
            duplicate_sno = next((entry for entry in draft if candidate.sno_explicit and entry.sno == candidate.sno), None)
            if duplicate_sno:
                result.conflicting_rows.append(MergeItem("conflict", candidate, duplicate_sno, "Duplicate serial number"))
                continue
            result.new_rows.append(MergeItem("new", candidate, reason="New row"))
        return result

    def apply(self, draft: list[OutlineEntry], analysis: MergeAnalysis, resolutions: dict[str, str] | None = None) -> list[OutlineEntry]:
        resolutions = resolutions or {}
        merged = [OutlineEntry(**vars(entry)) for entry in draft]
        next_sno = max((entry.sno for entry in merged), default=0) + 1

        def append(candidate: OutlineCandidate) -> None:
            nonlocal next_sno
            entry = candidate.to_outline_entry(next_sno)
            if any(existing.sno == entry.sno for existing in merged):
                entry.sno = next_sno
            next_sno = max(next_sno, entry.sno + 1)
            merged.append(entry)

        for item in analysis.new_rows:
            append(item.candidate)
        for item in analysis.conflicting_rows:
            action = resolutions.get(item.candidate.candidate_id, "keep_draft")
            if action == "use_candidate" and item.draft is not None:
                index = merged.index(next(entry for entry in merged if entry.sno == item.draft.sno))
                replacement = item.candidate.to_outline_entry(item.draft.sno)
                replacement.sno = item.draft.sno
                merged[index] = replacement
            elif action == "keep_both":
                append(item.candidate)
        return merged
