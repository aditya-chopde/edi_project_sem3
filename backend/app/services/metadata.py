import re
from dataclasses import dataclass


LINE_ID_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])([0-9]{8}[A-Za-z])(?![A-Za-z0-9])"
)
LINE_ID_START_PATTERN = re.compile(
    r"(?m)^[ \t]*(?=[0-9]{8}[A-Za-z](?![A-Za-z0-9]))"
)
_MARKDOWN_HEADER_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_TILDE_HEADER_PATTERN = re.compile(r"^\s*~{1,}\s*(.+?)\s*~*\s*$")


@dataclass(frozen=True)
class ChunkMetadata:
    book_number: str | None = None
    parvan: int | None = None
    line_id: str | None = None
    line_ids: tuple[str, ...] = ()
    section_header: str | None = None


def section_header_for_line(line: str) -> str | None:
    markdown_match = _MARKDOWN_HEADER_PATTERN.match(line)
    if markdown_match:
        return markdown_match.group(1).strip()
    tilde_match = _TILDE_HEADER_PATTERN.match(line)
    if tilde_match:
        return tilde_match.group(1).strip() or None
    return None


def extract_chunk_metadata(
    text: str, section_header: str | None = None
) -> ChunkMetadata:
    line_ids = tuple(dict.fromkeys(LINE_ID_PATTERN.findall(text)))
    primary_line_id = line_ids[0] if line_ids else None
    book_number = primary_line_id[:2] if primary_line_id else None
    return ChunkMetadata(
        book_number=book_number,
        parvan=int(book_number) if book_number is not None else None,
        line_id=primary_line_id,
        line_ids=line_ids,
        section_header=section_header,
    )


def build_embedding_text(
    text: str,
    *,
    book_number: str | None = None,
    parvan: int | None = None,
    line_ids: tuple[str, ...] | list[str] = (),
    section_header: str | None = None,
) -> str:
    metadata: list[str] = []
    if section_header:
        metadata.append(f"section_header={section_header}")
    if book_number:
        metadata.append(f"book_number={book_number}")
    if parvan is not None:
        metadata.append(f"parvan={parvan}")
    if line_ids:
        metadata.append(f"line_id={line_ids[0]}")
        if len(line_ids) > 1:
            metadata.append(f"line_ids={','.join(line_ids)}")
    if not metadata:
        return text
    return f"[{' | '.join(metadata)}]\n{text}"
