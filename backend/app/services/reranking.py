from threading import Lock
from typing import Sequence

import numpy as np
from sentence_transformers import CrossEncoder

from app import config
from app.models import Chunk
from app.services.device import resolve_device

_model: CrossEncoder | None = None
_model_lock = Lock()
_prediction_lock = Lock()


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                config.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _model = CrossEncoder(
                    config.RERANKER_MODEL,
                    max_length=config.RERANKER_MAX_LENGTH,
                    device=resolve_device(config.RERANKER_DEVICE, "reranking"),
                    cache_folder=str(config.MODEL_CACHE_DIR),
                )
    return _model


def rerank(
    query: str, chunks: Sequence[Chunk], top_k: int
) -> list[tuple[int, float]]:
    if top_k <= 0 or not chunks:
        return []
    if any(chunk.id is None for chunk in chunks):
        raise ValueError("All candidate chunks must be persisted before reranking")

    pairs = [(query, chunk.text) for chunk in chunks]
    with _prediction_lock:
        scores = np.asarray(
            _get_model().predict(
                pairs,
                batch_size=config.RERANKER_BATCH_SIZE,
                show_progress_bar=False,
            ),
            dtype=np.float64,
        ).reshape(-1)
    if scores.size != len(chunks):
        raise ValueError("The reranker must return one score per candidate chunk")
    if not np.isfinite(scores).all():
        raise ValueError("The reranker returned a non-finite score")

    ranked = sorted(
        (
            (int(chunk.id), float(score), position)
            for position, (chunk, score) in enumerate(zip(chunks, scores, strict=True))
            if chunk.id is not None
        ),
        key=lambda item: (-item[1], item[2]),
    )
    return [(chunk_id, score) for chunk_id, score, _ in ranked[:top_k]]
