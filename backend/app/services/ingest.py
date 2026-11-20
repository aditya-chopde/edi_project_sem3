import logging
import sys
import shutil
from pathlib import Path
from time import perf_counter

from sqlmodel import Session, select

from app import config
from app.database import engine
from app.models import Chunk, Document
from app.services.chunking import chunk_pages
from app.services.embeddings import embed_passages
from app.services.extraction import extract_document
from app.services.exports import export_chunks
from app.services.indexing import queue_index_update

logger = logging.getLogger(__name__)

try:
    import resource
except ImportError:
    resource = None


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
    logger.info(
        "Document ingestion status (document_id=%s, status=%s)",
        document_id,
        status,
    )


def _update_progress(document_id: str, percent: int, detail: str) -> None:
    bounded_percent = max(0, min(percent, 99))
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if document is None:
            raise ValueError(f"Document {document_id} no longer exists")
        if document.progress_percent == bounded_percent:
            return
        document.progress_percent = bounded_percent
        document.progress_detail = detail
        session.add(document)
        session.commit()
    logger.info(
        "Document ingestion progress (document_id=%s, progress=%d%%, detail=%s)",
        document_id,
        bounded_percent,
        detail,
    )


def ingest_document(document_id: str, raw_path: Path) -> None:
    total_started_at = perf_counter()
    try:
        logger.info("Started document ingestion (document_id=%s)", document_id)
        with Session(engine) as session:
            document = session.get(Document, document_id)
            if document is None:
                raise ValueError(f"Document {document_id} no longer exists")
            file_type = document.file_type
            language = document.language
        logger.info(
            "Preparing ingestion (document_id=%s, file_type=%s)",
            document_id,
            file_type,
        )

        _set_status(
            document_id,
            "extracting",
            error=None,
            progress_percent=0,
            progress_detail="Starting text extraction",
        )

        def update_extraction_progress(done: int, total: int) -> None:
            percent = 5 + int(20 * done / total) if total else 25
            _update_progress(
                document_id, percent, f"Extracted {done} of {total} pages"
            )

        stage_started_at = perf_counter()
        pages = extract_document(
            raw_path,
            file_type,
            progress_callback=update_extraction_progress,
        )
        logger.info(
            "Ingestion stage timing (document_id=%s, stage=extraction, "
            "elapsed_seconds=%.3f)",
            document_id,
            perf_counter() - stage_started_at,
        )
        _update_progress(document_id, 25, f"Extracted {len(pages)} pages")
        logger.info(
            "Text extraction complete (document_id=%s, pages=%d)",
            document_id,
            len(pages),
        )
        _set_status(
            document_id,
            "chunking",
            num_pages=len(pages),
            progress_percent=25,
            progress_detail="Starting page-aligned chunking",
        )

        def update_chunking_progress(done: int, total: int) -> None:
            percent = 25 + int(15 * done / total) if total else 40
            _update_progress(
                document_id, percent, f"Chunked {done} of {total} pages"
            )

        stage_started_at = perf_counter()
        text_chunks = chunk_pages(
            pages,
            progress_callback=update_chunking_progress,
        )
        logger.info(
            "Ingestion stage timing (document_id=%s, stage=chunking, "
            "elapsed_seconds=%.3f)",
            document_id,
            perf_counter() - stage_started_at,
        )
        _update_progress(document_id, 40, f"Created {len(text_chunks)} chunks")
        logger.info(
            "Chunking complete (document_id=%s, chunks=%d)",
            document_id,
            len(text_chunks),
        )
        _set_status(
            document_id,
            "embedding",
            num_chunks=len(text_chunks),
            progress_percent=40,
            progress_detail=f"Embedding {len(text_chunks)} chunks",
        )
        logger.info(
            "Generating passage embeddings (document_id=%s, model=%s, chunks=%d)",
            document_id,
            config.EMBEDDING_MODEL,
            len(text_chunks),
        )

        def update_embedding_progress(done: int, total: int) -> None:
            percent = 40 + int(45 * done / total) if total else 85
            _update_progress(
                document_id, percent, f"Embedded {done} of {total} chunks"
            )

        stage_started_at = perf_counter()
        vectors = embed_passages(
            [chunk.embedding_text for chunk in text_chunks],
            progress_callback=update_embedding_progress,
        )
        logger.info(
            "Ingestion stage timing (document_id=%s, stage=embedding, "
            "elapsed_seconds=%.3f)",
            document_id,
            perf_counter() - stage_started_at,
        )
        _update_progress(document_id, 85, f"Embedded {len(vectors)} chunks")
        logger.info(
            "Embedding complete (document_id=%s, vectors=%d)",
            document_id,
            len(vectors),
        )

        _set_status(
            document_id,
            "indexing",
            progress_percent=86,
            progress_detail="Saving chunks and updating search indexes",
        )
        stage_started_at = perf_counter()
        with Session(engine, expire_on_commit=False) as session:
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
                    book_number=chunk.book_number,
                    parvan=chunk.parvan,
                    line_id=chunk.line_id,
                    line_ids=list(chunk.line_ids),
                    section_header=chunk.section_header,
                )
                for chunk in text_chunks
            ]
            session.add_all(persisted_chunks)
            document.num_chunks = len(persisted_chunks)
            session.add(document)
            session.flush()
            session.commit()
            logger.info(
                "Saved chunks to database (document_id=%s, chunks=%d)",
                document_id,
                len(persisted_chunks),
            )
        logger.info(
            "Ingestion stage timing (document_id=%s, stage=database_insert, "
            "elapsed_seconds=%.3f)",
            document_id,
            perf_counter() - stage_started_at,
        )

        _update_progress(document_id, 89, "Saved chunks to the database")
        stage_started_at = perf_counter()
        export_path = export_chunks(document_id, persisted_chunks)
        logger.info(
            "Exported chunks (document_id=%s, path=%s)",
            document_id,
            export_path,
        )
        logger.info(
            "Ingestion stage timing (document_id=%s, stage=chunk_export, "
            "elapsed_seconds=%.3f)",
            document_id,
            perf_counter() - stage_started_at,
        )
        _update_progress(document_id, 92, "Exported processed chunks")
        indexed = queue_index_update(
            document_id, persisted_chunks, vectors
        ).result()
        if not indexed:
            export_path.unlink(missing_ok=True)
            logger.info(
                "Stopped ingestion because document was deleted (document_id=%s)",
                document_id,
            )
            return
        _update_progress(document_id, 99, "Updated dense and sparse indexes")
        logger.info(
            "Committed document to dense and sparse indexes "
            "(document_id=%s, vectors=%d)",
            document_id,
            len(vectors),
        )
        _set_status(
            document_id,
            "indexed",
            error=None,
            progress_percent=100,
            progress_detail="Ingestion complete",
        )
        peak_rss_mb = None
        if resource is not None:
            peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak_rss_mb = peak_rss / (
                1024 * 1024 if sys.platform == "darwin" else 1024
            )
        logger.info(
            "Document ingestion complete (document_id=%s, "
            "total_elapsed_seconds=%.3f, process_peak_rss_mb=%s)",
            document_id,
            perf_counter() - total_started_at,
            "unavailable" if peak_rss_mb is None else f"{peak_rss_mb:.1f}",
        )
    except Exception as error:
        message = str(error).strip() or error.__class__.__name__
        logger.exception(
            "Ingestion failed for document %s (elapsed_seconds=%.3f)",
            document_id,
            perf_counter() - total_started_at,
        )
        try:
            with Session(engine) as session:
                document = session.get(Document, document_id)
                if document is not None:
                    document.status = "failed"
                    document.error = message[:500]
                    document.progress_detail = "Ingestion failed"
                    session.add(document)
                    session.commit()
            logger.info(
                "Document ingestion status (document_id=%s, status=failed)",
                document_id,
            )
        except Exception:
            logger.exception("Could not save failed status for document %s", document_id)
