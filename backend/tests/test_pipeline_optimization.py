import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event, Lock
from unittest.mock import patch

import fitz
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

_test_dataset = tempfile.TemporaryDirectory(prefix="itihasa-tests-")
os.environ["ITIHASA_DATASET_DIR"] = str(Path(_test_dataset.name) / "dataset")

from app import config
from app import database as database_module
from app.database import engine as app_engine
from app.main import app
from app.models import Chunk, Document
from app.routers import documents as documents_router
from app.services import ingestion_queue
from app.services import indexes
from app.services.extraction import PageText, extract_document
from app.services.ingestion_queue import stop_ingestion_worker
from app.services.indexing import stop_indexing_worker
from app.services.ingest import ingest_document


def _memory_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


class FullIngestionTests(unittest.TestCase):
    def test_batch_insert_keeps_database_export_and_index_ids_aligned(self):
        document_id = "full-ingestion-test"
        raw_path = Path(_test_dataset.name) / "source.txt"
        raw_path.write_text("test", encoding="utf-8")
        export_path = config.PROCESSED_DIR / f"doc_{document_id}_chunks.jsonl"

        try:
            with TestClient(app):
                with Session(app_engine) as session:
                    session.add(
                        Document(
                            id=document_id,
                            title="Test document",
                            filename=raw_path.name,
                            file_type=".txt",
                            language="en",
                        )
                    )
                    session.commit()

                with (
                    patch(
                        "app.services.ingest.extract_document",
                        return_value=[
                            PageText(
                                page=1,
                                text="Historical evidence " * 80,
                            )
                        ],
                    ),
                    patch(
                        "app.services.ingest.embed_passages",
                        side_effect=lambda texts, progress_callback=None: np.ones(
                            (len(texts), 4),
                            dtype=np.float32,
                        ),
                    ),
                ):
                    ingest_document(document_id, raw_path)

                with Session(app_engine) as session:
                    document = session.get(Document, document_id)
                    chunks = session.exec(
                        select(Chunk).where(Chunk.document_id == document_id)
                    ).all()
                    self.assertEqual(document.status, "indexed")
                    self.assertEqual(document.progress_percent, 100)
                    exported = [
                        json.loads(line)
                        for line in export_path.read_text(encoding="utf-8").splitlines()
                    ]
                    self.assertEqual(
                        [item["chunk_db_id"] for item in exported],
                        [chunk.id for chunk in chunks],
                    )
                self.assertEqual(indexes.diagnostics_counts(), (len(chunks), len(chunks)))
        finally:
            stop_indexing_worker()
            with Session(app_engine) as session:
                document = session.get(Document, document_id)
                if document is not None:
                    for chunk in session.exec(
                        select(Chunk).where(Chunk.document_id == document_id)
                    ).all():
                        session.delete(chunk)
                    session.delete(document)
                    session.commit()
                indexes.rebuild_all(session)
            export_path.unlink(missing_ok=True)


class InterruptedIngestionRecoveryTests(unittest.TestCase):
    def test_resume_incomplete_and_finalize_committed_indexing_state(self):
        database_module.create_db_and_tables()
        document_ids = {"recover-indexed", "resume-embedding"}
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            raw_dir = root_path / "raw"
            processed_dir = root_path / "processed"
            resumable_path = raw_dir / "resume-embedding" / "resume.txt"
            resumable_path.parent.mkdir(parents=True)
            resumable_path.write_text("resume", encoding="utf-8")
            with Session(app_engine) as session:
                session.add(
                    Document(
                        id="recover-indexed",
                        title="Recover",
                        filename="recover.txt",
                        file_type=".txt",
                        language="en",
                        status="indexing",
                        num_chunks=1,
                    )
                )
                session.add(
                    Chunk(
                        document_id="recover-indexed",
                        chunk_index=0,
                        text="committed chunk",
                        page_start=1,
                        page_end=1,
                        language="en",
                    )
                )
                session.add(
                    Document(
                        id="resume-embedding",
                        title="Resume",
                        filename="resume.txt",
                        file_type=".txt",
                        language="en",
                        status="embedding",
                        progress_percent=45,
                    )
                )
                session.commit()

            try:
                with (
                    patch.object(config, "RAW_DIR", raw_dir),
                    patch.object(config, "PROCESSED_DIR", processed_dir),
                    patch.object(
                        ingestion_queue, "queue_document_ingestion"
                    ) as queue_ingestion,
                ):
                    ingestion_queue.recover_interrupted_ingestions()
                queue_ingestion.assert_called_once_with(
                    "resume-embedding",
                    resumable_path,
                )
                with Session(app_engine) as session:
                    recovered = session.get(Document, "recover-indexed")
                    resumed = session.get(Document, "resume-embedding")
                    self.assertEqual(recovered.status, "indexed")
                    self.assertEqual(recovered.progress_percent, 100)
                    self.assertEqual(resumed.status, "pending")
                    self.assertEqual(resumed.progress_percent, 0)
                self.assertTrue(
                    (processed_dir / "doc_recover-indexed_chunks.jsonl").is_file()
                )
            finally:
                with Session(app_engine) as session:
                    for document_id in document_ids:
                        document = session.get(Document, document_id)
                        if document is not None:
                            session.delete(document)
                    session.commit()


class IngestionQueueTests(unittest.TestCase):
    def test_queue_dispatches_work_to_single_worker(self):
        completed = Event()
        raw_path = Path(_test_dataset.name) / "queued.txt"
        with patch.object(
            ingestion_queue,
            "ingest_document",
            side_effect=lambda document_id, path: completed.set(),
        ):
            ingestion_queue.queue_document_ingestion("queued-doc", raw_path)
            self.assertTrue(completed.wait(timeout=5))
            stop_ingestion_worker()


class UploadDeduplicationTests(unittest.TestCase):
    def test_identical_upload_reuses_existing_document(self):
        with patch.object(
            documents_router, "queue_document_ingestion", return_value=None
        ):
            with TestClient(app) as client:
                first = client.post(
                    "/api/documents/upload",
                    files={"file": ("source.txt", b"identical source text", "text/plain")},
                    data={"title": "Original"},
                )
                duplicate = client.post(
                    "/api/documents/upload",
                    files={"file": ("copy.txt", b"identical source text", "text/plain")},
                    data={"title": "Duplicate"},
                )

        self.assertEqual(first.status_code, 202)
        self.assertEqual(duplicate.status_code, 202)
        self.assertEqual(duplicate.json()["id"], first.json()["id"])
        self.assertEqual(duplicate.json()["title"], "Original")

        with Session(app_engine) as session:
            records = session.exec(select(Document)).all()
        self.assertEqual(len(records), 1)
        self.assertIsNotNone(records[0].content_sha256)


class LegacyHashBackfillTests(unittest.TestCase):
    def test_existing_raw_file_is_hashed_for_duplicate_lookup(self):
        engine = _memory_engine()
        content = b"legacy source bytes"
        with tempfile.TemporaryDirectory() as root:
            raw_dir = Path(root) / "raw"
            raw_path = raw_dir / "legacy-doc" / "legacy.txt"
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(content)
            with Session(engine) as session:
                legacy = Document(
                    id="legacy-doc",
                    title="Legacy",
                    filename="legacy.txt",
                    file_type=".txt",
                    language="en",
                )
                session.add(legacy)
                session.commit()
                with patch.object(config, "RAW_DIR", raw_dir):
                    duplicate = documents_router._find_duplicate(
                        session,
                        "new-upload",
                        hashlib.sha256(content).hexdigest(),
                    )
                self.assertEqual(duplicate.id, "legacy-doc")
                self.assertIsNotNone(
                    session.get(Document, "legacy-doc").content_sha256
                )
        engine.dispose()


class DatabaseMigrationTests(unittest.TestCase):
    def test_existing_sqlite_schema_gets_hash_and_progress_columns(self):
        with tempfile.TemporaryDirectory() as root:
            legacy_engine = create_engine(f"sqlite:///{Path(root) / 'legacy.db'}")
            with legacy_engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE document ("
                        "id VARCHAR PRIMARY KEY, title VARCHAR NOT NULL, "
                        "filename VARCHAR NOT NULL, file_type VARCHAR NOT NULL, "
                        "language VARCHAR NOT NULL, historical_period VARCHAR, "
                        "source_url VARCHAR, status VARCHAR NOT NULL, error VARCHAR, "
                        "num_pages INTEGER NOT NULL, num_chunks INTEGER NOT NULL, "
                        "created_at DATETIME NOT NULL)"
                    )
                )
            with (
                patch.object(database_module, "engine", legacy_engine),
                patch.object(config, "DATASET_DIR", Path(root)),
            ):
                database_module.create_db_and_tables()
                columns = {
                    column["name"]
                    for column in inspect(legacy_engine).get_columns("document")
                }
                indexes_present = {
                    index["name"] for index in inspect(legacy_engine).get_indexes("document")
                }
            self.assertTrue(
                {"content_sha256", "progress_percent", "progress_detail"} <= columns
            )
            self.assertIn("uq_document_content_sha256", indexes_present)
            legacy_engine.dispose()


class IndexBatchTests(unittest.TestCase):
    def test_batch_adds_vectors_once_and_rebuilds_sparse_once(self):
        engine = _memory_engine()
        try:
            with Session(engine, expire_on_commit=False) as session:
                updates = []
                for index in range(2):
                    document_id = f"doc-{index}"
                    session.add(
                        Document(
                            id=document_id,
                            title=document_id,
                            filename=f"{index}.txt",
                            file_type=".txt",
                            language="en",
                        )
                    )
                    chunk = Chunk(
                        document_id=document_id,
                        chunk_index=0,
                        text=f"evidence {index}",
                        page_start=1,
                        page_end=1,
                        language="en",
                    )
                    session.add(chunk)
                    session.flush()
                    updates.append(
                        (
                            document_id,
                            [chunk],
                            np.array([[1.0, float(index)]], dtype=np.float32),
                        )
                    )

                with (
                    patch.object(indexes, "_dense_index", None),
                    patch.object(indexes, "_dense_chunk_ids", []),
                    patch.object(indexes, "_persist_dense") as persist_dense,
                    patch.object(indexes, "rebuild_sparse") as rebuild_sparse,
                ):
                    indexed_ids = indexes.add_document_batch(session, updates)
                    self.assertEqual(indexed_ids, {"doc-0", "doc-1"})
                    self.assertEqual(indexes._dense_index.ntotal, 2)
                    old_chunk_id = updates[0][1][0].id
                    session.delete(updates[0][1][0])
                    session.commit()
                    replacement = Chunk(
                        document_id="doc-0",
                        chunk_index=0,
                        text="updated evidence",
                        page_start=1,
                        page_end=1,
                        language="en",
                    )
                    session.add(replacement)
                    session.flush()
                    indexes.add_document_batch(
                        session,
                        [
                            (
                                "doc-0",
                                [replacement],
                                np.array([[0.5, 0.5]], dtype=np.float32),
                            )
                        ],
                    )
                    self.assertEqual(indexes._dense_index.ntotal, 2)
                    self.assertNotIn(old_chunk_id, indexes._dense_chunk_ids)
                    self.assertIn(replacement.id, indexes._dense_chunk_ids)
                    indexes.add_document_batch(
                        session,
                        [
                            (
                                "doc-0",
                                [replacement],
                                np.array([[0.25, 0.75]], dtype=np.float32),
                            )
                        ],
                    )
                    self.assertEqual(indexes._dense_index.ntotal, 2)
                    self.assertEqual(indexes._dense_chunk_ids.count(replacement.id), 1)
                    self.assertEqual(persist_dense.call_count, 3)
                    self.assertEqual(rebuild_sparse.call_count, 3)
        finally:
            engine.dispose()


class SparsePersistenceTests(unittest.TestCase):
    def test_restart_loads_saved_bm25_without_retokenizing(self):
        engine = _memory_engine()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "bm25.pkl"
            try:
                with Session(engine) as session:
                    session.add(
                        Document(
                            id="doc",
                            title="doc",
                            filename="doc.txt",
                            file_type=".txt",
                            language="en",
                        )
                    )
                    session.add(
                        Chunk(
                            document_id="doc",
                            chunk_index=0,
                            text="historical evidence",
                            page_start=1,
                            page_end=1,
                            language="en",
                        )
                    )
                    session.commit()

                with Session(engine) as session:
                    with patch.object(config, "BM25_INDEX_PATH", path):
                        indexes.rebuild_sparse(session)
                        indexes._bm25 = None
                        indexes._sparse_chunk_ids = []
                        indexes._sparse_corpus = []
                        with patch.object(
                            indexes,
                            "_tokens",
                            side_effect=AssertionError("unexpected retokenization"),
                        ):
                            indexes._load_sparse(session)
                self.assertEqual(indexes._sparse_chunk_ids, [1])
                self.assertIsNotNone(indexes._bm25)
            finally:
                engine.dispose()


class ParallelOcrTests(unittest.TestCase):
    def test_pdf_ocr_is_bounded_and_page_order_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            pdf_path = Path(root) / "pages.pdf"
            pdf = fitz.open()
            first = pdf.new_page()
            first.insert_text(
                (72, 72),
                "A text layer with sufficient content to avoid OCR on this page.",
            )
            pdf.new_page()
            pdf.new_page()
            pdf.save(pdf_path)
            pdf.close()

            active = 0
            peak = 0
            lock = Lock()

            def fake_ocr(path: str, page_index: int) -> str:
                nonlocal active, peak
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.08 if page_index == 1 else 0.03)
                with lock:
                    active -= 1
                return f"OCR page {page_index + 1}"

            progress = []
            with patch(
                "app.services.extraction._ocr_pdf_page",
                side_effect=fake_ocr,
            ):
                pages = extract_document(
                    pdf_path,
                    ".pdf",
                    lambda done, total: progress.append((done, total)),
                )

        self.assertEqual([page.page for page in pages], [1, 2, 3])
        self.assertEqual([page.text for page in pages[1:]], ["OCR page 2", "OCR page 3"])
        self.assertEqual(peak, min(config.OCR_WORKERS, 2))
        self.assertEqual(sorted(done for done, _ in progress), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
