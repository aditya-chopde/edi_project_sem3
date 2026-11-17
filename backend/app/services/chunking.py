from dataclasses import dataclass
import logging

from app import config
from app.services.extraction import PageText

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str
    page_start: int
    page_end: int


def _split_page(text: str) -> list[str]:
    if config.CHUNK_SIZE <= 0:
        raise ValueError("ITIHASA_CHUNK_SIZE must be greater than zero")
    if config.CHUNK_OVERLAP < 0 or config.CHUNK_OVERLAP >= config.CHUNK_SIZE:
        raise ValueError("ITIHASA_CHUNK_OVERLAP must be between zero and chunk size")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + config.CHUNK_SIZE, len(text))
        if end < len(text):
            for separator in ("\n\n", "\n", " "):
                boundary = text.rfind(separator, start, end)
                if boundary > start:
                    end = min(end, boundary + len(separator))
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        next_start = max(start + 1, end - config.CHUNK_OVERLAP)
        start = next_start
    return chunks


def chunk_pages(pages: list[PageText]) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    logger.info(
        "Splitting extracted text by page (chunk_size=%d, overlap=%d)",
        config.CHUNK_SIZE,
        config.CHUNK_OVERLAP,
    )
    for page in pages:
        page_chunks = _split_page(page.text)
        logger.debug(
            "Split page into chunks (page=%d, characters=%d, chunks=%d)",
            page.page,
            len(page.text),
            len(page_chunks),
        )
        for text in page_chunks:
            chunk_index = len(chunks)
            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    text=text,
                    page_start=page.page,
                    page_end=page.page,
                )
            )
            logger.debug(
                "Created chunk (chunk_index=%d, page=%d, characters=%d)",
                chunk_index,
                page.page,
                len(text),
            )
    return chunks
