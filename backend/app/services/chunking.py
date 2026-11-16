from dataclasses import dataclass

from app import config
from app.services.extraction import PageText


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
    for page in pages:
        for text in _split_page(page.text):
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    text=text,
                    page_start=page.page,
                    page_end=page.page,
                )
            )
    return chunks
