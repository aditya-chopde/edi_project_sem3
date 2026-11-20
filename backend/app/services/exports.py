import json
from pathlib import Path
from typing import Sequence

from app import config
from app.models import Chunk


def export_chunks(document_id: str, chunks: Sequence[Chunk]) -> Path:
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    export_path = config.PROCESSED_DIR / f"doc_{document_id}_chunks.jsonl"
    temporary_path = export_path.with_suffix(".jsonl.tmp")
    with temporary_path.open("w", encoding="utf-8") as export_file:
        for chunk in chunks:
            export_file.write(
                json.dumps(
                    {
                        "chunk_db_id": chunk.id,
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "language": chunk.language,
                        "book_number": chunk.book_number,
                        "parvan": chunk.parvan,
                        "line_id": chunk.line_id,
                        "line_ids": chunk.line_ids,
                        "section_header": chunk.section_header,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    temporary_path.replace(export_path)
    return export_path
