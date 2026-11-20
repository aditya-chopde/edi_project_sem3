from dataclasses import dataclass
import logging
from typing import Callable

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import config
from app.services.extraction import PageText
from app.services.metadata import (
    ChunkMetadata,
    LINE_ID_START_PATTERN,
    build_embedding_text,
    extract_chunk_metadata,
    section_header_for_line,
)

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    book_number: str | None = None
    parvan: int | None = None
    line_id: str | None = None
    line_ids: tuple[str, ...] = ()
    section_header: str | None = None

    @property
    def embedding_text(self) -> str:
        return build_embedding_text(
            self.text,
            book_number=self.book_number,
            parvan=self.parvan,
            line_ids=self.line_ids,
            section_header=self.section_header,
        )


def _token_length(text: str) -> int:
    encoding = tiktoken.get_encoding(config.TIKTOKEN_ENCODING)
    return len(encoding.encode(text, disallowed_special=()))


def _splitter() -> RecursiveCharacterTextSplitter:
    if config.CHUNK_SIZE <= 0:
        raise ValueError("ITIHASA_CHUNK_SIZE must be greater than zero")
    if config.CHUNK_OVERLAP < 0 or config.CHUNK_OVERLAP >= config.CHUNK_SIZE:
        raise ValueError("ITIHASA_CHUNK_OVERLAP must be between zero and chunk size")

    return RecursiveCharacterTextSplitter(
        separators=[*config.CHUNK_SEPARATORS, ""],
        is_separator_regex=True,
        keep_separator="start",
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        length_function=_token_length,
    )


def _section_blocks(text: str) -> list[tuple[str | None, str]]:
    blocks: list[tuple[str | None, str]] = []
    active_header: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        parsed_header = section_header_for_line(line.rstrip("\r\n"))
        if parsed_header is not None:
            if current_lines:
                blocks.append((active_header, "".join(current_lines)))
            active_header = parsed_header
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        blocks.append((active_header, "".join(current_lines)))
    return blocks


def _record_blocks(text: str) -> list[str]:
    starts = [match.start() for match in LINE_ID_START_PATTERN.finditer(text)]
    if not starts:
        return [text]
    boundaries = [0, *starts[1:]]
    return [
        text[start:end]
        for start, end in zip(
            boundaries, [*boundaries[1:], len(text)], strict=True
        )
    ]


def _split_page(text: str) -> list[tuple[str, ChunkMetadata]]:
    splitter = _splitter()
    chunks: list[tuple[str, ChunkMetadata]] = []
    for section_header, section_text in _section_blocks(text):
        for record_text in _record_blocks(section_text):
            record_metadata = extract_chunk_metadata(record_text, section_header)
            for chunk_text in splitter.split_text(record_text):
                cleaned_text = chunk_text.strip()
                if not cleaned_text:
                    continue
                chunk_metadata = extract_chunk_metadata(
                    cleaned_text, section_header
                )
                line_ids = tuple(
                    dict.fromkeys(
                        (*record_metadata.line_ids, *chunk_metadata.line_ids)
                    )
                )
                primary_line_id = (
                    record_metadata.line_id
                    or chunk_metadata.line_id
                )
                book_number = (
                    primary_line_id[:2] if primary_line_id else None
                )
                chunks.append(
                    (
                        cleaned_text,
                        ChunkMetadata(
                            book_number=book_number,
                            parvan=(
                                int(book_number)
                                if book_number is not None
                                else None
                            ),
                            line_id=primary_line_id,
                            line_ids=line_ids,
                            section_header=section_header,
                        ),
                    )
                )
    return chunks


def chunk_pages(
    pages: list[PageText],
    progress_callback: ProgressCallback | None = None,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    logger.info(
        "Splitting extracted text by page (chunk_tokens=%d, overlap_tokens=%d)",
        config.CHUNK_SIZE,
        config.CHUNK_OVERLAP,
    )
    for page_number, page in enumerate(pages, start=1):
        page_chunks = _split_page(page.text)
        logger.debug(
            "Split page into chunks (page=%d, characters=%d, chunks=%d)",
            page.page,
            len(page.text),
            len(page_chunks),
        )
        for text, metadata in page_chunks:
            chunk_index = len(chunks)
            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    text=text,
                    page_start=page.page,
                    page_end=page.page,
                    book_number=metadata.book_number,
                    parvan=metadata.parvan,
                    line_id=metadata.line_id,
                    line_ids=metadata.line_ids,
                    section_header=metadata.section_header,
                )
            )
            logger.debug(
                "Created chunk (chunk_index=%d, page=%d, characters=%d)",
                chunk_index,
                page.page,
                len(text),
            )
        if progress_callback:
            progress_callback(page_number, len(pages))
    return chunks
