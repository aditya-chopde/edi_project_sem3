import json
import logging
import shutil
from pathlib import Path

from sqlmodel import Session, select

from app import config
from app.database import engine
from app.models import Chunk, Document
from app.services.chunking import chunk_pages
from app.services.embeddings import embed_passages
from app.services.extraction import extract_document
from app.services.indexes import add_document_vectors, rebuild_sparse

logger = logging.getLogger(__name__)


def _set_status(document_id: str, status: str, **updates: object) -> None:
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if document is None:
            raise ValueError(f"Document {document_id} no longer exists")
        document.status = status
        for field, value in updates.items():
            setattr(document, field, value)
        session.add(document)
        session.commit()


def ingest_document(document_id: str, raw_path: Path) -> None:
    try:
        with Session(engine) as session:
            document = session.get(Document, document_id)
            if document is None:
                raise ValueError(f"Document {document_id} no longer exists")
            file_type = document.file_type
            language = document.language

        _set_status(document_id, "extracting", error=None)
        pages = extract_document(raw_path, file_type)
        _set_status(document_id, "chunking", num_pages=len(pages))
        text_chunks = chunk_pages(pages)
        _set_status(document_id, "embedding", num_chunks=len(text_chunks))
        vectors = embed_passages([chunk.text for chunk in text_chunks])

        with Session(engine) as session:
            document = session.get(Document, document_id)
            if document is None:
                raise ValueError(f"Document {document_id} no longer exists")
            old_chunks = list(
                session.exec(select(Chunk).where(Chunk.document_id == document_id)).all()
            )
            for old_chunk in old_chunks:
                session.delete(old_chunk)
            persisted_chunks = [
                Chunk(
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    language=language,
                )
                for chunk in text_chunks
            ]
            session.add_all(persisted_chunks)
            document.num_chunks = len(persisted_chunks)
            session.add(document)
            session.commit()
            for chunk in persisted_chunks:
                session.refresh(chunk)

            config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
            export_path = config.PROCESSED_DIR / f"doc_{document_id}_chunks.jsonl"
            temporary_path = export_path.with_suffix(".jsonl.tmp")
            with temporary_path.open("w", encoding="utf-8") as export_file:
                for chunk in persisted_chunks:
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
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            temporary_path.replace(export_path)

        export_path = config.PROCESSED_DIR / f"doc_{document_id}_chunks.jsonl"
        with Session(engine) as session:
            if not add_document_vectors(
                session, document_id, persisted_chunks, vectors
            ):
                export_path.unlink(missing_ok=True)
                return
        with Session(engine) as session:
            rebuild_sparse(session)
        _set_status(document_id, "indexed", error=None)
    except Exception as error:
        message = str(error).strip() or error.__class__.__name__
        logger.exception("Ingestion failed for document %s", document_id)
        try:
            _set_status(document_id, "failed", error=message[:500])
        except Exception:
            logger.exception("Could not save failed status for document %s", document_id)
