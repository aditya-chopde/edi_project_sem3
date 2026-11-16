import pickle
import re
from pathlib import Path
from threading import RLock
from typing import Sequence

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sqlmodel import Session, select

from app import config
from app.models import Chunk, Document
from app.services.embeddings import embed_passages, embed_query

_lock = RLock()
_dense_index: faiss.Index | None = None
_dense_chunk_ids: list[int] = []
_bm25: BM25Okapi | None = None
_sparse_chunk_ids: list[int] = []


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


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
    _write_pickle(config.FAISS_META_PATH, {"chunk_ids": _dense_chunk_ids})


def _persist_sparse() -> None:
    tokenized = []
    if _bm25 is not None:
        tokenized = _bm25.corpus
    _write_pickle(
        config.BM25_INDEX_PATH,
        {"chunk_ids": _sparse_chunk_ids, "tokenized_corpus": tokenized},
    )


def rebuild_sparse(session: Session) -> None:
    global _bm25, _sparse_chunk_ids
    with _lock:
        chunks = _all_chunks(session)
        _sparse_chunk_ids = [int(chunk.id) for chunk in chunks if chunk.id is not None]
        corpus = [_tokens(chunk.text) for chunk in chunks]
        _bm25 = BM25Okapi(corpus) if corpus else None
        config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        _persist_sparse()


def _rebuild_dense(chunks: Sequence[Chunk]) -> None:
    global _dense_index, _dense_chunk_ids
    if not chunks:
        _dense_index = None
        _dense_chunk_ids = []
        config.FAISS_INDEX_PATH.unlink(missing_ok=True)
        _write_pickle(config.FAISS_META_PATH, {"chunk_ids": []})
        return
    vectors = embed_passages([chunk.text for chunk in chunks])
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
                loaded_index is not None
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
        rebuild_sparse(session)


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
                        _dense_index.reconstruct(
                            positions[int(chunk.id)]
                        )
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


def search_dense(query: str, top_k: int) -> list[int]:
    if not query:
        return []
    with _lock:
        if _dense_index is None or _dense_index.ntotal == 0:
            return []
    query_vector = embed_query(query)
    with _lock:
        if _dense_index is None or _dense_index.ntotal == 0:
            return []
        scores, indexes = _dense_index.search(
            query_vector, min(top_k, _dense_index.ntotal)
        )
        return [
            _dense_chunk_ids[index]
            for index, score in zip(indexes[0], scores[0], strict=True)
            if index >= 0 and np.isfinite(score)
        ]


def search_sparse(query: str, top_k: int) -> list[int]:
    with _lock:
        if _bm25 is None:
            return []
        scores = _bm25.get_scores(_tokens(query))
        ranked_indexes = sorted(
            range(len(scores)), key=lambda index: scores[index], reverse=True
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
