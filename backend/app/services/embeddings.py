from threading import Lock

import numpy as np
from sentence_transformers import SentenceTransformer

from app import config

_model: SentenceTransformer | None = None
_model_lock = Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                config.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _model = SentenceTransformer(
                    config.EMBEDDING_MODEL,
                    cache_folder=str(config.MODEL_CACHE_DIR),
                )
    return _model


def embed_passages(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    model = _get_model()
    vectors = model.encode(
        [f"passage: {text}" for text in texts],
        batch_size=config.EMBEDDING_BATCH_SIZE,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    vector = _get_model().encode(
        [f"query: {text}"],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vector, dtype=np.float32)
