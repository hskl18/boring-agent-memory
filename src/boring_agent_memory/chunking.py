from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace


CHUNKER_VERSION = 2
DEFAULT_CHUNK_SIZE = 1600


@dataclass(frozen=True)
class TextChunk:
    id: str
    heading: str
    heading_key: str
    ordinal: int
    start_line: int
    end_line: int
    content: str
    content_hash: str


@dataclass(frozen=True)
class _Block:
    heading: str
    heading_key: str
    start_line: int
    end_line: int
    content: str
    protected: bool = False


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
LIST_RE = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
BLOCKQUOTE_RE = re.compile(r"^\s*>\s?")


def chunk_text(
    document_id: str,
    content: str,
    extension: str,
    max_chars: int = DEFAULT_CHUNK_SIZE,
) -> tuple[TextChunk, ...]:
    """Split source text into deterministic, citation-ready chunks."""
    if max_chars <= 0:
        return (_make_chunk(document_id, "", "document", 0, 1, _line_count(content), content),)

    if extension.lower() in {".md", ".mdx"}:
        blocks = _markdown_blocks(content)
    else:
        blocks = _plain_blocks(content)
    if not blocks:
        blocks = [_Block("", "document", 1, 1, content)]

    chunks: list[TextChunk] = []
    section_ordinals: dict[str, int] = {}
    identity_keys: list[tuple[str, str]] = []
    pending: list[_Block] = []
    pending_size = 0
    pending_key: str | None = None

    def flush() -> None:
        nonlocal pending, pending_size, pending_key
        if not pending:
            return
        key = pending[0].heading_key
        ordinal = section_ordinals.get(key, 0)
        section_ordinals[key] = ordinal + 1
        chunk_content = "\n\n".join(block.content for block in pending).strip()
        identity_key = (_semantic_heading_key(key), chunk_content)
        identity_keys.append(identity_key)
        chunks.append(
            _make_chunk(
                document_id=document_id,
                heading=pending[0].heading,
                heading_key=key,
                ordinal=ordinal,
                start_line=pending[0].start_line,
                end_line=pending[-1].end_line,
                content=chunk_content,
            )
        )
        pending = []
        pending_size = 0
        pending_key = None

    for original in blocks:
        for block in _split_oversized_plain_block(original, max_chars):
            addition = len(block.content) + (2 if pending else 0)
            if pending and (block.heading_key != pending_key or pending_size + addition > max_chars):
                flush()
            pending.append(block)
            pending_key = block.heading_key
            pending_size += len(block.content) + (2 if len(pending) > 1 else 0)
            if block.protected and len(block.content) > max_chars:
                flush()
    flush()
    identity_totals = Counter(identity_keys)
    duplicate_structure = hashlib.sha256(
        json.dumps(
            identity_keys,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return tuple(
        replace(
            chunk,
            id=_chunk_id(
                document_id,
                chunk.heading_key,
                chunk.content,
                identity_occurrence,
                identity_totals[identity_key],
                (
                    duplicate_structure
                    if identity_totals[identity_key] > 1
                    else None
                ),
            ),
        )
        for chunk, identity_key, identity_occurrence in _identity_occurrence_rows(
            chunks,
            identity_keys,
        )
    )


def _markdown_blocks(content: str) -> list[_Block]:
    lines = content.splitlines()
    blocks: list[_Block] = []
    heading_stack: list[tuple[int, str, str]] = []
    heading_occurrences: dict[str, int] = {}
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            heading_stack = [item for item in heading_stack if item[0] < level]
            parent_key = "/".join(item[2] for item in heading_stack)
            base_key = f"{parent_key}/{_slug(text)}".strip("/")
            occurrence = heading_occurrences.get(base_key, 0) + 1
            heading_occurrences[base_key] = occurrence
            local_key = f"{_slug(text)}@{occurrence}"
            heading_stack.append((level, text, local_key))
            heading, heading_key = _heading_context(heading_stack)
            blocks.append(_Block(heading, heading_key, index + 1, index + 1, line, True))
            index += 1
            continue

        heading, heading_key = _heading_context(heading_stack)
        fence_match = FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            fence_char = marker[0]
            start = index
            index += 1
            while index < len(lines):
                if re.match(rf"^\s{{0,3}}{re.escape(fence_char)}{{{len(marker)},}}\s*$", lines[index]):
                    index += 1
                    break
                index += 1
            blocks.append(
                _Block(
                    heading,
                    heading_key,
                    start + 1,
                    index,
                    "\n".join(lines[start:index]),
                    True,
                )
            )
            continue

        if _starts_table(lines, index):
            start = index
            index += 2
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                index += 1
            blocks.append(
                _Block(heading, heading_key, start + 1, index, "\n".join(lines[start:index]), True)
            )
            continue

        if LIST_RE.match(line) or BLOCKQUOTE_RE.match(line):
            matcher = LIST_RE if LIST_RE.match(line) else BLOCKQUOTE_RE
            start = index
            index += 1
            while index < len(lines) and lines[index].strip():
                if HEADING_RE.match(lines[index]) or FENCE_RE.match(lines[index]):
                    break
                if matcher is BLOCKQUOTE_RE and not BLOCKQUOTE_RE.match(lines[index]):
                    break
                index += 1
            blocks.append(
                _Block(heading, heading_key, start + 1, index, "\n".join(lines[start:index]), True)
            )
            continue

        start = index
        index += 1
        while index < len(lines) and lines[index].strip():
            if (
                HEADING_RE.match(lines[index])
                or FENCE_RE.match(lines[index])
                or LIST_RE.match(lines[index])
                or BLOCKQUOTE_RE.match(lines[index])
                or _starts_table(lines, index)
            ):
                break
            index += 1
        blocks.append(_Block(heading, heading_key, start + 1, index, "\n".join(lines[start:index])))
    return blocks


def _plain_blocks(content: str) -> list[_Block]:
    lines = content.splitlines()
    if not lines:
        return [_Block("", "document", 1, 1, content)]
    blocks: list[_Block] = []
    start = 0
    for index, line in enumerate(lines + [""]):
        if line.strip():
            continue
        if index > start:
            blocks.append(
                _Block("", "document", start + 1, index, "\n".join(lines[start:index]))
            )
        start = index + 1
    return blocks


def _split_oversized_plain_block(block: _Block, max_chars: int) -> list[_Block]:
    if block.protected or len(block.content) <= max_chars:
        return [block]
    lines = block.content.splitlines() or [block.content]
    output: list[_Block] = []
    current: list[str] = []
    current_start = block.start_line

    def append_current(end_line: int) -> None:
        nonlocal current, current_start
        if current:
            output.append(
                _Block(
                    block.heading,
                    block.heading_key,
                    current_start,
                    end_line,
                    "\n".join(current),
                )
            )
            current = []

    for offset, line in enumerate(lines):
        line_number = block.start_line + offset
        if len(line) > max_chars:
            append_current(line_number - 1)
            words = line.split()
            piece: list[str] = []
            for word in words:
                if piece and len(" ".join([*piece, word])) > max_chars:
                    output.append(
                        _Block(
                            block.heading,
                            block.heading_key,
                            line_number,
                            line_number,
                            " ".join(piece),
                        )
                    )
                    piece = []
                if len(word) > max_chars:
                    if piece:
                        output.append(
                            _Block(
                                block.heading,
                                block.heading_key,
                                line_number,
                                line_number,
                                " ".join(piece),
                            )
                        )
                        piece = []
                    output.extend(
                        _Block(
                            block.heading,
                            block.heading_key,
                            line_number,
                            line_number,
                            word[start : start + max_chars],
                        )
                        for start in range(0, len(word), max_chars)
                    )
                else:
                    piece.append(word)
            if piece:
                output.append(
                    _Block(
                        block.heading,
                        block.heading_key,
                        line_number,
                        line_number,
                        " ".join(piece),
                    )
                )
            current_start = line_number + 1
            continue
        candidate = "\n".join([*current, line])
        if current and len(candidate) > max_chars:
            append_current(line_number - 1)
            current_start = line_number
        current.append(line)
    append_current(block.end_line)
    return output


def _make_chunk(
    document_id: str,
    heading: str,
    heading_key: str,
    ordinal: int,
    start_line: int,
    end_line: int,
    content: str,
    identity_ordinal: int = 0,
    identity_total: int = 1,
    duplicate_structure: str | None = None,
) -> TextChunk:
    chunk_id = _chunk_id(
        document_id,
        heading_key,
        content,
        identity_ordinal,
        identity_total,
        duplicate_structure,
    )
    return TextChunk(
        id=chunk_id,
        heading=heading,
        heading_key=heading_key,
        ordinal=ordinal,
        start_line=start_line,
        end_line=end_line,
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def _chunk_id(
    document_id: str,
    heading_key: str,
    content: str,
    identity_ordinal: int,
    identity_total: int,
    duplicate_structure: str | None,
) -> str:
    stable_key = json.dumps(
        [
            document_id,
            CHUNKER_VERSION,
            _semantic_heading_key(heading_key),
            content,
            identity_ordinal,
            identity_total,
            duplicate_structure,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(stable_key.encode("utf-8")).hexdigest()


def _identity_occurrence_rows(
    chunks: list[TextChunk],
    identity_keys: list[tuple[str, str]],
) -> list[tuple[TextChunk, tuple[str, str], int]]:
    occurrences: dict[tuple[str, str], int] = {}
    rows: list[tuple[TextChunk, tuple[str, str], int]] = []
    for chunk, identity_key in zip(chunks, identity_keys):
        occurrence = occurrences.get(identity_key, 0)
        occurrences[identity_key] = occurrence + 1
        rows.append((chunk, identity_key, occurrence))
    return rows


def _heading_context(stack: list[tuple[int, str, str]]) -> tuple[str, str]:
    if not stack:
        return "", "document"
    return " > ".join(item[1] for item in stack), "/".join(item[2] for item in stack)


def _starts_table(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and "|" in lines[index]
        and bool(TABLE_SEPARATOR_RE.match(lines[index + 1]))
    )


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value) or "section"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _semantic_heading_key(heading_key: str) -> str:
    return "/".join(part.rsplit("@", 1)[0] for part in heading_key.split("/"))


def _line_count(content: str) -> int:
    return max(1, len(content.splitlines()))
