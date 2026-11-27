from threading import Lock
from typing import Callable

import numpy as np
from sentence_transformers import SentenceTransformer

from app import config
from app.services.device import resolve_device

_model: SentenceTransformer | None = None
_model_lock = Lock()
ProgressCallback = Callable[[int, int], None]


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                config.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _model = SentenceTransformer(
                    config.EMBEDDING_MODEL,
                    cache_folder=str(config.MODEL_CACHE_DIR),
                    device=resolve_device(config.EMBEDDING_DEVICE, "embeddings"),
                )
    return _model


def embed_passages(
    texts: list[str],
    progress_callback: ProgressCallback | None = None,
) -> np.ndarray:
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    model = _get_model()
    embeddings = []
    for start in range(0, len(texts), config.EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + config.EMBEDDING_BATCH_SIZE]
        vectors = model.encode(
            [f"passage: {text}" for text in batch],
            batch_size=config.EMBEDDING_BATCH_SIZE,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        embeddings.append(np.asarray(vectors, dtype=np.float32))
        if progress_callback:
            progress_callback(start + len(batch), len(texts))
    return np.concatenate(embeddings, axis=0)


def embed_query(text: str) -> np.ndarray:
    vector = _get_model().encode(
        [f"query: {text}"],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vector, dtype=np.float32)
