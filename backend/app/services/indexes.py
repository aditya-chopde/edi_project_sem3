import logging
import pickle
import unicodedata
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Sequence

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sqlmodel import Session, select

from app import config
from app.models import Chunk, Document
from app.services.embeddings import embed_passages, embed_query
from app.services.metadata import build_embedding_text

_lock = RLock()
_dense_index: faiss.Index | None = None
_dense_chunk_ids: list[int] = []
_bm25: BM25Okapi | None = None
_sparse_chunk_ids: list[int] = []
_sparse_corpus: list[list[str]] = []
logger = logging.getLogger(__name__)

_LEGACY_EMBEDDING_MODEL = "intfloat/multilingual-e5-base"


def _tokens(text: str) -> list[str]:
    normalized_text = unicodedata.normalize("NFC", text).casefold()
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized_text:
        if (
            character.isalnum()
            or character == "_"
            or unicodedata.category(character).startswith("M")
        ):
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return tokens


def _chunk_search_text(chunk: Chunk) -> str:
    return build_embedding_text(
        chunk.text,
        book_number=chunk.book_number,
        parvan=chunk.parvan,
        line_ids=chunk.line_ids,
        section_header=chunk.section_header,
    )


def _all_chunks(session: Session) -> list[Chunk]:
    return list(session.exec(select(Chunk).order_by(Chunk.id)).all())


def _write_pickle(path: Path, value: object) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("wb") as file:
        pickle.dump(value, file, protocol=pickle.HIGHEST_PROTOCOL)
    temporary_path.replace(path)


def _persist_dense() -> None:
    if _dense_index is not None:
        temporary_path = config.FAISS_INDEX_PATH.with_suffix(".index.tmp")
        faiss.write_index(_dense_index, str(temporary_path))
        temporary_path.replace(config.FAISS_INDEX_PATH)
    else:
        config.FAISS_INDEX_PATH.unlink(missing_ok=True)
    _write_pickle(
        config.FAISS_META_PATH,
        {
            "chunk_ids": _dense_chunk_ids,
            "embedding_model": config.EMBEDDING_MODEL,
        },
    )


def _persist_sparse() -> None:
    _write_pickle(
        config.BM25_INDEX_PATH,
        {
            "chunk_ids": _sparse_chunk_ids,
            "tokenized_corpus": _sparse_corpus,
            "bm25": _bm25,
            "tokenizer_version": 2,
        },
    )


def rebuild_sparse(session: Session) -> None:
    global _bm25, _sparse_chunk_ids, _sparse_corpus
    with _lock:
        chunks = _all_chunks(session)
        _sparse_chunk_ids = [int(chunk.id) for chunk in chunks if chunk.id is not None]
        _sparse_corpus = [_tokens(_chunk_search_text(chunk)) for chunk in chunks]
        _bm25 = BM25Okapi(_sparse_corpus) if _sparse_corpus else None
        config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        _persist_sparse()


def _load_sparse(session: Session) -> None:
    global _bm25, _sparse_chunk_ids, _sparse_corpus
    expected_ids = [
        int(chunk.id)
        for chunk in _all_chunks(session)
        if chunk.id is not None
    ]
    try:
        with config.BM25_INDEX_PATH.open("rb") as file:
            metadata = pickle.load(file)
        chunk_ids = metadata["chunk_ids"]
        corpus = metadata["tokenized_corpus"]
        if (
            metadata.get("tokenizer_version") != 2
            or chunk_ids != expected_ids
            or len(corpus) != len(expected_ids)
        ):
            raise ValueError("Saved sparse index does not match database chunks")
        saved_bm25 = metadata.get("bm25")
        if saved_bm25 is not None and not isinstance(saved_bm25, BM25Okapi):
            raise TypeError("Saved BM25 object has an unexpected type")
        _sparse_chunk_ids = list(chunk_ids)
        _sparse_corpus = corpus
        _bm25 = saved_bm25 or (BM25Okapi(_sparse_corpus) if _sparse_corpus else None)
        if saved_bm25 is None:
            _persist_sparse()
    except (
        OSError,
        EOFError,
        KeyError,
        ValueError,
        TypeError,
        AttributeError,
        pickle.UnpicklingError,
    ):
        rebuild_sparse(session)


def _rebuild_dense(chunks: Sequence[Chunk]) -> None:
    global _dense_index, _dense_chunk_ids
    if not chunks:
        _dense_index = None
        _dense_chunk_ids = []
        config.FAISS_INDEX_PATH.unlink(missing_ok=True)
        _write_pickle(
            config.FAISS_META_PATH,
            {"chunk_ids": [], "embedding_model": config.EMBEDDING_MODEL},
        )
        return
    vectors = embed_passages([_chunk_search_text(chunk) for chunk in chunks])
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    _dense_index = index
    _dense_chunk_ids = [int(chunk.id) for chunk in chunks if chunk.id is not None]
    _persist_dense()


def load_indexes(session: Session) -> None:
    global _dense_index, _dense_chunk_ids
    with _lock:
        config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        chunks = _all_chunks(session)
        chunk_ids = [int(chunk.id) for chunk in chunks if chunk.id is not None]
        try:
            with config.FAISS_META_PATH.open("rb") as file:
                metadata = pickle.load(file)
            saved_ids = metadata["chunk_ids"]
            loaded_index = (
                faiss.read_index(str(config.FAISS_INDEX_PATH))
                if config.FAISS_INDEX_PATH.exists()
                else None
            )
            if loaded_index is None and not saved_ids:
                _dense_index = None
                _dense_chunk_ids = []
            elif (
                (
                    metadata.get("embedding_model") == config.EMBEDDING_MODEL
                    or (
                        metadata.get("embedding_model") is None
                        and config.EMBEDDING_MODEL == _LEGACY_EMBEDDING_MODEL
                    )
                )
                and loaded_index is not None
                and loaded_index.ntotal == len(saved_ids)
                and set(saved_ids) == set(chunk_ids)
            ):
                _dense_index = loaded_index
                _dense_chunk_ids = list(saved_ids)
            else:
                _rebuild_dense(chunks)
        except (
            OSError,
            EOFError,
            KeyError,
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
            pickle.UnpicklingError,
        ):
            _rebuild_dense(chunks)
        _load_sparse(session)


def add_vectors(chunks: Sequence[Chunk], vectors: np.ndarray) -> None:
    global _dense_index, _dense_chunk_ids
    if not chunks:
        return
    with _lock:
        if _dense_index is None:
            _dense_index = faiss.IndexFlatIP(vectors.shape[1])
        elif _dense_index.d != vectors.shape[1]:
            raise ValueError("Embedding dimensions do not match the saved FAISS index")
        _dense_index.add(vectors)
        _dense_chunk_ids.extend(int(chunk.id) for chunk in chunks if chunk.id is not None)
        config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        _persist_dense()


def add_document_vectors(
    session: Session,
    document_id: str,
    chunks: Sequence[Chunk],
    vectors: np.ndarray,
) -> bool:
    with _lock:
        if session.get(Document, document_id) is None:
            return False
        add_vectors(chunks, vectors)
        return True


def add_document_batch(
    session: Session,
    updates: Sequence[tuple[str, Sequence[Chunk], np.ndarray]],
) -> set[str]:
    global _dense_index, _dense_chunk_ids
    with _lock:
        requested_ids = {document_id for document_id, _, _ in updates}
        existing_ids = (
            set(
                session.exec(
                    select(Document.id).where(Document.id.in_(requested_ids))
                ).all()
            )
            if requested_ids
            else set()
        )
        valid_updates = [
            (document_id, chunks, vectors)
            for document_id, chunks, vectors in updates
            if document_id in existing_ids
        ]
        if not valid_updates:
            return set()

        vector_updates = [
            (document_id, chunks, vectors)
            for document_id, chunks, vectors in valid_updates
            if chunks
        ]
        chunk_ids: list[int] = []
        vector_batches: list[np.ndarray] = []
        for _, chunks, vectors in vector_updates:
            if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
                raise ValueError("Each chunk must have exactly one embedding vector")
            if any(chunk.id is None for chunk in chunks):
                raise ValueError("All chunks must be persisted before indexing")
            chunk_ids.extend(int(chunk.id) for chunk in chunks if chunk.id is not None)
            vector_batches.append(np.asarray(vectors, dtype=np.float32))
        combined_vectors: np.ndarray | None = None
        if vector_batches:
            combined_vectors = (
                vector_batches[0]
                if len(vector_batches) == 1
                else np.concatenate(vector_batches, axis=0)
            )
            if len(chunk_ids) != combined_vectors.shape[0]:
                raise ValueError("Embedding and chunk counts do not match")
            if (
                _dense_index is not None
                and _dense_index.d != combined_vectors.shape[1]
            ):
                raise ValueError(
                    "Embedding dimensions do not match the saved FAISS index"
                )

        active_chunk_ids = set(
            session.exec(select(Chunk.id).where(Chunk.id.is_not(None))).all()
        )
        replacement_chunk_ids = {
            int(chunk.id)
            for _, chunks, _ in valid_updates
            for chunk in chunks
            if chunk.id is not None
        }
        dense_changed = False
        if _dense_index is not None:
            retained_positions = [
                position
                for position, chunk_id in enumerate(_dense_chunk_ids)
                if (
                    chunk_id in active_chunk_ids
                    and chunk_id not in replacement_chunk_ids
                )
            ]
            if len(retained_positions) != len(_dense_chunk_ids):
                retained_ids = [
                    _dense_chunk_ids[position] for position in retained_positions
                ]
                if retained_positions:
                    retained_vectors = np.vstack(
                        [
                            _dense_index.reconstruct(position)
                            for position in retained_positions
                        ]
                    )
                    rebuilt_index = faiss.IndexFlatIP(_dense_index.d)
                    rebuilt_index.add(retained_vectors)
                    _dense_index = rebuilt_index
                else:
                    _dense_index = None
                _dense_chunk_ids = retained_ids
                dense_changed = True
                logger.info(
                    "Removed stale dense vectors before indexing "
                    "(retained_vectors=%d)",
                    len(retained_ids),
                )

        if combined_vectors is not None:
            if _dense_index is None:
                _dense_index = faiss.IndexFlatIP(combined_vectors.shape[1])
            faiss_started_at = perf_counter()
            _dense_index.add(combined_vectors)
            _dense_chunk_ids.extend(chunk_ids)
            logger.info(
                "Dense batch added (documents=%d, vectors=%d, elapsed_seconds=%.3f)",
                len(vector_updates),
                len(chunk_ids),
                perf_counter() - faiss_started_at,
            )
            dense_changed = True

        if dense_changed:
            persist_started_at = perf_counter()
            config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
            _persist_dense()
            logger.info(
                "Dense index persisted (vectors=%d, elapsed_seconds=%.3f)",
                len(_dense_chunk_ids),
                perf_counter() - persist_started_at,
            )
        sparse_started_at = perf_counter()
        rebuild_sparse(session)
        logger.info(
            "Sparse index rebuilt for document batch (documents=%d, "
            "elapsed_seconds=%.3f)",
            len(valid_updates),
            perf_counter() - sparse_started_at,
        )
        return {document_id for document_id, _, _ in valid_updates}


def rebuild_all(session: Session) -> None:
    global _dense_index, _dense_chunk_ids
    with _lock:
        chunks = _all_chunks(session)
        if not chunks:
            _rebuild_dense(chunks)
        elif _dense_index is not None:
            positions = {
                chunk_id: position
                for position, chunk_id in enumerate(_dense_chunk_ids)
            }
            if all(chunk.id in positions for chunk in chunks):
                vectors = np.vstack(
                    [
                        _dense_index.reconstruct(positions[int(chunk.id)])
                        for chunk in chunks
                    ]
                )
                index = faiss.IndexFlatIP(vectors.shape[1])
                index.add(vectors)
                _dense_index = index
                _dense_chunk_ids = [int(chunk.id) for chunk in chunks]
                _persist_dense()
            else:
                _rebuild_dense(chunks)
        else:
            _rebuild_dense(chunks)
        rebuild_sparse(session)


def search_dense(
    query: str, top_k: int, allowed_ids: set[int] | None = None
) -> list[int]:
    if not query or top_k <= 0 or allowed_ids == set():
        return []
    with _lock:
        if _dense_index is None or _dense_index.ntotal == 0:
            return []
    query_vector = embed_query(query)
    with _lock:
        if _dense_index is None or _dense_index.ntotal == 0:
            return []
        search_limit = (
            _dense_index.ntotal
            if allowed_ids is not None
            else min(top_k, _dense_index.ntotal)
        )
        scores, indexes = _dense_index.search(query_vector, search_limit)
        return [
            _dense_chunk_ids[index]
            for index, score in zip(indexes[0], scores[0], strict=True)
            if (
                index >= 0
                and np.isfinite(score)
                and (
                    allowed_ids is None
                    or _dense_chunk_ids[index] in allowed_ids
                )
            )
        ][:top_k]


def search_sparse(
    query: str, top_k: int, allowed_ids: set[int] | None = None
) -> list[int]:
    if not query or top_k <= 0 or allowed_ids == set():
        return []
    with _lock:
        if _bm25 is None:
            return []
        scores = _bm25.get_scores(_tokens(query))
        ranked_indexes = sorted(
            (
                index
                for index, chunk_id in enumerate(_sparse_chunk_ids)
                if allowed_ids is None or chunk_id in allowed_ids
            ),
            key=lambda index: scores[index],
            reverse=True,
        )
        return [
            _sparse_chunk_ids[index]
            for index in ranked_indexes[:top_k]
            if scores[index] > 0
        ]


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[int]], top_k: int, rrf_k: int = config.RRF_K
) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranked_list in ranked_lists:
        for rank, chunk_id in enumerate(ranked_list, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]


def diagnostics_counts() -> tuple[int, int]:
    with _lock:
        return (
            0 if _dense_index is None else int(_dense_index.ntotal),
            0 if _bm25 is None else len(_sparse_chunk_ids),
        )
