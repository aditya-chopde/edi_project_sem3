from concurrent.futures import Future
from dataclasses import dataclass
import logging
from queue import Empty, Queue
from threading import Lock, Thread
from time import monotonic
from typing import Sequence

import numpy as np
from sqlmodel import Session

from app import config
from app.database import engine
from app.models import Chunk
from app.services.indexes import add_document_batch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _IndexRequest:
    document_id: str
    chunks: Sequence[Chunk]
    vectors: np.ndarray
    future: Future[bool]


_queue: Queue[_IndexRequest | None] = Queue(maxsize=config.INDEX_QUEUE_MAX_DOCUMENTS)
_worker_lock = Lock()
_worker_thread: Thread | None = None
_stopping = False


def _process_batch(requests: list[_IndexRequest]) -> None:
    started_at = monotonic()
    updates = [
        (request.document_id, request.chunks, request.vectors)
        for request in requests
    ]
    try:
        with Session(engine) as session:
            indexed_ids = add_document_batch(session, updates)
        for request in requests:
            if not request.future.cancelled():
                request.future.set_result(request.document_id in indexed_ids)
        logger.info(
            "Index batch completed (documents=%d, indexed=%d, elapsed_seconds=%.3f)",
            len(requests),
            len(indexed_ids),
            monotonic() - started_at,
        )
    except Exception as error:
        logger.exception(
            "Index batch failed (documents=%d, elapsed_seconds=%.3f)",
            len(requests),
            monotonic() - started_at,
        )
        for request in requests:
            if not request.future.cancelled():
                request.future.set_exception(error)


def _run_worker() -> None:
    while True:
        first_request = _queue.get()
        if first_request is None:
            return

        requests = [first_request]
        deadline = monotonic() + config.INDEX_BATCH_WINDOW_SECONDS
        should_stop = False
        while len(requests) < config.INDEX_BATCH_MAX_DOCUMENTS:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            try:
                request = _queue.get(timeout=remaining)
            except Empty:
                break
            if request is None:
                should_stop = True
                break
            requests.append(request)

        _process_batch(requests)
        if should_stop:
            return


def queue_index_update(
    document_id: str, chunks: Sequence[Chunk], vectors: np.ndarray
) -> Future[bool]:
    global _worker_thread, _stopping
    future: Future[bool] = Future()
    request = _IndexRequest(document_id, chunks, vectors, future)
    with _worker_lock:
        if _stopping:
            raise RuntimeError("The indexing worker is shutting down")
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = Thread(
                target=_run_worker,
                name="itihasa-indexing",
                daemon=False,
            )
            _worker_thread.start()
        _queue.put(request)
    return future


def stop_indexing_worker() -> None:
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
