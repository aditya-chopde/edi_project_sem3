from dataclasses import dataclass
import logging
from pathlib import Path
from queue import Queue
from threading import Lock, Thread
from typing import Sequence

from sqlmodel import Session, func, select

from app import config
from app.database import engine
from app.models import Chunk, Document
from app.services.exports import export_chunks
from app.services.ingest import ingest_document

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _IngestionRequest:
    document_id: str
    raw_path: Path


_queue: Queue[_IngestionRequest | None] = Queue(
    maxsize=config.INGESTION_QUEUE_MAX_DOCUMENTS
)
_worker_lock = Lock()
_worker_thread: Thread | None = None
_stopping = False


def _mark_failed(document_id: str, error: Exception) -> None:
    try:
        with Session(engine) as session:
            document = session.get(Document, document_id)
            if document is not None:
                message = str(error).strip() or error.__class__.__name__
                document.status = "failed"
                document.error = message[:500]
                document.progress_detail = "Ingestion worker failed"
                session.add(document)
                session.commit()
    except Exception:
        logger.exception(
            "Could not save ingestion worker failure (document_id=%s)",
            document_id,
        )


def _run_worker() -> None:
    while True:
        request = _queue.get()
        if request is None:
            return
        try:
            ingest_document(request.document_id, request.raw_path)
        except Exception as error:
            logger.exception(
                "Unexpected ingestion worker failure (document_id=%s)",
                request.document_id,
            )
            _mark_failed(request.document_id, error)


def queue_document_ingestion(document_id: str, raw_path: Path) -> None:
    global _worker_thread, _stopping
    request = _IngestionRequest(document_id, raw_path)
    with _worker_lock:
        if _stopping:
            raise RuntimeError("The ingestion worker is shutting down")
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = Thread(
                target=_run_worker,
                name="itihasa-ingestion",
                daemon=False,
            )
            _worker_thread.start()
        _queue.put(request)
    logger.info("Queued document ingestion (document_id=%s)", document_id)


def stop_ingestion_worker() -> None:
    global _worker_thread, _stopping
    with _worker_lock:
        worker = _worker_thread
        if worker is None:
            return
        _stopping = True
        _queue.put(None)
    worker.join()
    with _worker_lock:
        _worker_thread = None
        _stopping = False


def recover_interrupted_ingestions() -> None:
    processing_statuses: Sequence[str] = (
        "pending",
        "extracting",
        "chunking",
        "embedding",
        "indexing",
    )
    pending: list[_IngestionRequest] = []
    with Session(engine, expire_on_commit=False) as session:
        documents = session.exec(
            select(Document).where(Document.status.in_(processing_statuses))
        ).all()
        for document in documents:
            chunk_count = session.exec(
                select(func.count(Chunk.id)).where(
                    Chunk.document_id == document.id
                )
            ).one()
            raw_path = (
                config.RAW_DIR / document.id / document.filename
            )
            if (
                document.status == "indexing"
                and document.num_chunks > 0
                and chunk_count == document.num_chunks
            ):
                chunks = list(
                    session.exec(
                        select(Chunk)
                        .where(Chunk.document_id == document.id)
                        .order_by(Chunk.id)
                    ).all()
                )
                export_chunks(document.id, chunks)
                document.status = "indexed"
                document.progress_percent = 100
                document.progress_detail = "Recovered indexed data after restart"
                document.error = None
                logger.info(
                    "Recovered indexed document after restart (document_id=%s)",
                    document.id,
                )
            elif raw_path.is_file():
                document.status = "pending"
                document.progress_percent = 0
                document.progress_detail = "Resuming ingestion after restart"
                document.error = None
                pending.append(_IngestionRequest(document.id, raw_path))
            else:
                document.status = "failed"
                document.error = (
                    "Ingestion was interrupted and the stored raw file is missing"
                )
                document.progress_detail = "Unable to resume ingestion"
                logger.error(
                    "Cannot resume interrupted document because its raw file is "
                    "missing (document_id=%s)",
                    document.id,
                )
            session.add(document)
        session.commit()

    for request in pending:
        queue_document_ingestion(request.document_id, request.raw_path)
