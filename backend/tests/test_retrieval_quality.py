import unittest
import pickle
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app import config
from app import database as database_module
from app.models import Chunk, Document
from app.schemas import QueryRequest
from app.services.chunking import _token_length, chunk_pages
from app.services.extraction import PageText
from app.services.indexes import _tokens, reciprocal_rank_fusion
from app.services import indexes
from app.services.llm import GeneratedAnswer
from app.services import retrieval, reranking


def _memory_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


class StructuralChunkingTests(unittest.TestCase):
    def test_chunks_preserve_record_ids_headers_and_page_boundaries(self):
        source = (
            "# Sabha Parvan\n"
            "01001065a\n"
            "Editorial correction: the verse citation is preserved here.\n"
            "The following commentary explains the correction in context.\n"
            "01001066b Another errata entry with its own verse reference.\n"
        )
        with (
            patch.object(config, "CHUNK_SIZE", 512),
            patch.object(config, "CHUNK_OVERLAP", 100),
        ):
            chunks = chunk_pages(
                [
                    PageText(page=4, text=source),
                    PageText(page=5, text="Continuation on the next page."),
                ]
            )

        first_page_chunks = [chunk for chunk in chunks if chunk.page_start == 4]
        self.assertEqual(len(first_page_chunks), 2)
        first, second = first_page_chunks
        self.assertEqual(first.line_id, "01001065a")
        self.assertEqual(first.book_number, "01")
        self.assertEqual(first.parvan, 1)
        self.assertEqual(first.section_header, "Sabha Parvan")
        self.assertIn("verse citation", first.text)
        self.assertEqual(second.line_id, "01001066b")
        self.assertEqual(second.section_header, "Sabha Parvan")
        self.assertTrue(all(chunk.page_start == chunk.page_end for chunk in chunks))
        self.assertTrue(all(_token_length(chunk.text) <= 512 for chunk in chunks))
        self.assertIn("section_header=Sabha Parvan", first.embedding_text)
        self.assertIn("line_id=01001065a", first.embedding_text)

    def test_long_unbroken_text_is_still_split_to_token_limit(self):
        with (
            patch.object(config, "CHUNK_SIZE", 512),
            patch.object(config, "CHUNK_OVERLAP", 90),
        ):
            chunks = chunk_pages([PageText(page=2, text="x" * 8000)])

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(_token_length(chunk.text) <= 512 for chunk in chunks))

    def test_sparse_tokens_keep_identifiers_and_unicode_diacritics(self):
        tokens = _tokens("01001065a Ṛgveda नमः देवनागरी")

        self.assertIn("01001065a", tokens)
        self.assertIn("ṛgveda", tokens)
        self.assertIn("नमः", tokens)
        self.assertIn("देवनागरी", tokens)

    def test_rrf_keeps_unique_candidates_in_fused_order(self):
        fused = reciprocal_rank_fusion([[10, 11], [11, 12]], top_k=3)

        self.assertEqual([chunk_id for chunk_id, _ in fused], [11, 10, 12])


class RerankingTests(unittest.TestCase):
    def test_cross_encoder_scores_return_highest_candidates(self):
        chunks = [
            Chunk(
                id=index,
                document_id="doc",
                chunk_index=index,
                text=f"evidence {index}",
                page_start=1,
                page_end=1,
                language="en",
            )
            for index in range(1, 5)
        ]

        class FakeCrossEncoder:
            def predict(self, pairs, batch_size, show_progress_bar):
                self.pairs = pairs
                return [0.1, 0.9, 0.3, 0.7]

        fake_model = FakeCrossEncoder()
        with patch.object(reranking, "_get_model", return_value=fake_model):
            results = reranking.rerank("question", chunks, top_k=2)

        self.assertEqual(results, [(2, 0.9), (4, 0.7)])
        self.assertEqual(len(fake_model.pairs), 4)
        self.assertEqual(fake_model.pairs[0], ("question", "evidence 1"))

    def test_query_sends_only_top_five_reranked_chunks_to_generator(self):
        engine = _memory_engine()
        try:
            with Session(engine) as session:
                session.add(
                    Document(
                        id="doc",
                        title="Historical source",
                        filename="source.txt",
                        file_type=".txt",
                        language="en",
                    )
                )
                session.add_all(
                    [
                        Chunk(
                            id=index,
                            document_id="doc",
                            chunk_index=index,
                            text=f"evidence {index}",
                            page_start=index,
                            page_end=index,
                            language="en",
                            line_id="01001065a" if index == 1 else None,
                            line_ids=["01001065a"] if index == 1 else [],
                            book_number="01" if index == 1 else None,
                            parvan=1 if index == 1 else None,
                        )
                        for index in range(1, 31)
                    ]
                )
                session.commit()

                with (
                    patch.object(
                        retrieval,
                        "search_dense",
                        side_effect=lambda question, top_k, allowed_ids=None: [
                            chunk_id
                            for chunk_id in range(1, 31)
                            if allowed_ids is None or chunk_id in allowed_ids
                        ][:top_k],
                    ),
                    patch.object(
                        retrieval,
                        "search_sparse",
                        side_effect=lambda question, top_k, allowed_ids=None: [
                            chunk_id
                            for chunk_id in range(30, 0, -1)
                            if allowed_ids is None or chunk_id in allowed_ids
                        ][:top_k],
                    ),
                    patch.object(
                        retrieval,
                        "rerank",
                        side_effect=lambda question, chunks, top_k: [
                            (chunk.id, float(30 - chunk.id))
                            for chunk in reversed(chunks[:5])
                        ],
                    ) as mock_rerank,
                    patch.object(
                        retrieval,
                        "generate_answer",
                        return_value=GeneratedAnswer(
                            answer="Verified answer",
                            cited_chunk_ids=[1, 30, 999],
                        ),
                    ) as mock_generate,
                ):
                    response = retrieval.answer_query(
                        session, "historical question", "en"
                    )

                self.assertEqual(len(mock_rerank.call_args.args[1]), 25)
                self.assertEqual(len(mock_generate.call_args.args[2].split("\n\n")), 5)
                self.assertEqual(len(response.retrieval.fused), 25)
                self.assertEqual(len(response.retrieval.reranked), 5)
                self.assertEqual(len(response.retrieval.chunk_ids), 5)
                self.assertEqual(response.used_chunk_ids, [1, 30])
                self.assertEqual(
                    [citation.page_start for citation in response.citations], [1, 30]
                )
        finally:
            engine.dispose()

    def test_exact_metadata_filters_are_passed_to_both_retrievers(self):
        engine = _memory_engine()
        try:
            with Session(engine) as session:
                session.add(
                    Document(
                        id="doc",
                        title="Historical source",
                        filename="source.txt",
                        file_type=".txt",
                        language="en",
                    )
                )
                chunk = Chunk(
                    document_id="doc",
                    chunk_index=0,
                    text="identified passage",
                    page_start=8,
                    page_end=8,
                    language="en",
                    line_id="01001065a",
                    line_ids=["01001065a"],
                    book_number="01",
                    parvan=1,
                    section_header="Sabha Parvan",
                )
                session.add(chunk)
                session.commit()
                session.refresh(chunk)
                chunk_id = chunk.id

                with (
                    patch.object(
                        retrieval,
                        "search_dense",
                        return_value=[chunk_id],
                    ) as dense_search,
                    patch.object(
                        retrieval,
                        "search_sparse",
                        return_value=[chunk_id],
                    ) as sparse_search,
                    patch.object(
                        retrieval,
                        "rerank",
                        return_value=[(chunk_id, 0.9)],
                    ),
                    patch.object(
                        retrieval,
                        "generate_answer",
                        return_value=GeneratedAnswer(
                            answer="Verified answer",
                            cited_chunk_ids=[chunk_id],
                        ),
                    ),
                ):
                    response = retrieval.answer_query(
                        session,
                        "01001065a",
                        "en",
                        book_number="01",
                        parvan=1,
                        line_id="01001065a",
                        section_header="Sabha Parvan",
                    )

                self.assertEqual(dense_search.call_args.args[2], {chunk_id})
                self.assertEqual(sparse_search.call_args.args[2], {chunk_id})
                self.assertEqual(response.used_chunk_ids, [chunk_id])
                self.assertEqual(
                    len(
                        session.exec(
                            select(Chunk).where(Chunk.line_id == "01001065a")
                        ).all()
                    ),
                    1,
                )
        finally:
            engine.dispose()


class QueryRequestFilterTests(unittest.TestCase):
    def test_metadata_filters_are_optional_and_bounded(self):
        request = QueryRequest(
            question="Where is this identifier discussed?",
            line_id="01001065a",
            parvan=1,
        )

        self.assertEqual(request.line_id, "01001065a")
        self.assertIsNone(request.book_number)
        with self.assertRaises(ValueError):
            QueryRequest(question="Question", parvan=100)
        with self.assertRaises(ValueError):
            QueryRequest(question="Question", line_id="01001065")


class MetadataMigrationTests(unittest.TestCase):
    def test_existing_chunk_table_gets_search_metadata_columns(self):
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
                connection.execute(
                    text(
                        "CREATE TABLE chunk ("
                        "id INTEGER PRIMARY KEY, document_id VARCHAR NOT NULL, "
                        "chunk_index INTEGER NOT NULL, text TEXT NOT NULL, "
                        "page_start INTEGER NOT NULL, page_end INTEGER NOT NULL, "
                        "language VARCHAR NOT NULL, "
                        "FOREIGN KEY(document_id) REFERENCES document(id))"
                    )
                )
            with (
                patch.object(database_module, "engine", legacy_engine),
                patch.object(config, "DATASET_DIR", Path(root)),
            ):
                database_module.create_db_and_tables()
                columns = {
                    column["name"]
                    for column in inspect(legacy_engine).get_columns("chunk")
                }

            self.assertTrue(
                {
                    "book_number",
                    "parvan",
                    "line_id",
                    "line_ids",
                    "section_header",
                }
                <= columns
            )
            legacy_engine.dispose()


class EmbeddingModelMigrationTests(unittest.TestCase):
    def test_legacy_e5_base_faiss_index_loads_without_reembedding(self):
        engine = _memory_engine()
        try:
            with Session(engine) as session:
                session.add(
                    Document(
                        id="legacy-doc",
                        title="Legacy",
                        filename="legacy.txt",
                        file_type=".txt",
                        language="en",
                    )
                )
                chunk = Chunk(
                    document_id="legacy-doc",
                    chunk_index=0,
                    text="existing vector",
                    page_start=1,
                    page_end=1,
                    language="en",
                )
                session.add(chunk)
                session.commit()
                session.refresh(chunk)
                with tempfile.TemporaryDirectory() as root:
                    root_path = Path(root)
                    index_dir = root_path / "index"
                    index_dir.mkdir()
                    metadata_path = index_dir / "faiss_meta.pkl"
                    with metadata_path.open("wb") as file:
                        pickle.dump({"chunk_ids": [chunk.id]}, file)
                    legacy_index = indexes.faiss.IndexFlatIP(768)
                    legacy_index.add(np.zeros((1, 768), dtype=np.float32))
                    index_path = index_dir / "faiss.index"
                    indexes.faiss.write_index(legacy_index, str(index_path))

                    with (
                        patch.object(config, "INDEX_DIR", index_dir),
                        patch.object(config, "FAISS_META_PATH", metadata_path),
                        patch.object(config, "FAISS_INDEX_PATH", index_path),
                        patch.object(config, "BM25_INDEX_PATH", index_dir / "bm25.pkl"),
                        patch.object(
                            config,
                            "EMBEDDING_MODEL",
                            "intfloat/multilingual-e5-base",
                        ),
                        patch.object(indexes, "_rebuild_dense") as rebuild_dense,
                        patch.object(indexes, "_load_sparse"),
                    ):
                        indexes.load_indexes(session)

                    rebuild_dense.assert_not_called()
        finally:
            engine.dispose()

    def test_faiss_index_from_different_model_is_rebuilt(self):
        engine = _memory_engine()
        try:
            with Session(engine) as session:
                session.add(
                    Document(
                        id="doc",
                        title="Historical source",
                        filename="source.txt",
                        file_type=".txt",
                        language="en",
                    )
                )
                chunk = Chunk(
                    document_id="doc",
                    chunk_index=0,
                    text="passage",
                    page_start=1,
                    page_end=1,
                    language="en",
                )
                session.add(chunk)
                session.commit()
                session.refresh(chunk)
                with tempfile.TemporaryDirectory() as root:
                    root_path = Path(root)
                    index_dir = root_path / "index"
                    index_dir.mkdir()
                    metadata_path = index_dir / "faiss_meta.pkl"
                    with metadata_path.open("wb") as file:
                        pickle.dump(
                            {
                                "chunk_ids": [chunk.id],
                                "embedding_model": "intfloat/multilingual-e5-base",
                            },
                            file,
                        )
                    with (
                        patch.object(config, "INDEX_DIR", index_dir),
                        patch.object(config, "FAISS_META_PATH", metadata_path),
                        patch.object(config, "FAISS_INDEX_PATH", index_dir / "faiss.index"),
                        patch.object(config, "BM25_INDEX_PATH", index_dir / "bm25.pkl"),
                        patch.object(
                            config,
                            "EMBEDDING_MODEL",
                            "intfloat/multilingual-e5-large",
                        ),
                        patch.object(indexes, "_rebuild_dense") as rebuild_dense,
                        patch.object(indexes, "_load_sparse"),
                    ):
                        indexes.load_indexes(session)

                rebuild_dense.assert_called_once()
                self.assertEqual(
                    rebuild_dense.call_args.args[0][0].text,
                    "passage",
                )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
