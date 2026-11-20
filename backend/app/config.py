import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

DATASET_DIR = Path(
    os.getenv("ITIHASA_DATASET_DIR", str(BACKEND_DIR / "dataset"))
).expanduser().resolve()
RAW_DIR = DATASET_DIR / "raw"
PROCESSED_DIR = DATASET_DIR / "processed"
INDEX_DIR = DATASET_DIR / "index"
MODEL_CACHE_DIR = DATASET_DIR / "models"
DB_PATH = DATASET_DIR / "itihasa.db"

FAISS_INDEX_PATH = INDEX_DIR / "faiss.index"
BM25_INDEX_PATH = INDEX_DIR / "bm25.pkl"
FAISS_META_PATH = INDEX_DIR / "faiss_meta.pkl"

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".txt",
    ".md",
    ".docx",
    ".epub",
    ".csv",
}
CHUNK_SIZE = int(os.getenv("ITIHASA_CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("ITIHASA_CHUNK_OVERLAP", "90"))
TIKTOKEN_ENCODING = os.getenv("ITIHASA_TIKTOKEN_ENCODING", "cl100k_base")
CHUNK_SEPARATORS = [
    "\n\n------------------------------------------------------------------------\n\n",
    "\n\n",
    r"\n(?=[0-9]{8}[a-zA-Z ])",
    " ",
]
EMBEDDING_MODEL = os.getenv(
    "ITIHASA_EMBEDDING_MODEL", "intfloat/multilingual-e5-base"
)
EMBEDDING_DEVICE = os.getenv("ITIHASA_EMBEDDING_DEVICE", "cpu")
EMBEDDING_BATCH_SIZE = int(os.getenv("ITIHASA_EMBEDDING_BATCH_SIZE", "32"))
RERANKER_MODEL = os.getenv(
    "ITIHASA_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
)
RERANKER_DEVICE = os.getenv("ITIHASA_RERANKER_DEVICE", "cpu")
RERANKER_MAX_LENGTH = int(os.getenv("ITIHASA_RERANKER_MAX_LENGTH", "768"))
RERANKER_BATCH_SIZE = int(os.getenv("ITIHASA_RERANKER_BATCH_SIZE", "8"))
OCR_DPI = 300
OCR_LANGS = os.getenv("TESSERACT_LANGS", "eng+hin+mar")
OCR_WORKERS = int(os.getenv("ITIHASA_OCR_WORKERS", "2"))
if OCR_WORKERS < 1:
    raise ValueError("ITIHASA_OCR_WORKERS must be at least one")
INDEX_BATCH_WINDOW_SECONDS = 0.25
INDEX_BATCH_MAX_DOCUMENTS = 16
INDEX_QUEUE_MAX_DOCUMENTS = 32
INGESTION_QUEUE_MAX_DOCUMENTS = 32
DENSE_TOP_K = 30
SPARSE_TOP_K = 30
FUSED_TOP_K = 25
RERANKED_TOP_K = 5
RRF_K = 60
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
CORS_ORIGINS = ["http://localhost:3000"]
LOG_LEVEL = os.getenv("ITIHASA_LOG_LEVEL", "INFO").upper()
if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    raise ValueError(
        "ITIHASA_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
    )
