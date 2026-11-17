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
CHUNK_OVERLAP = int(os.getenv("ITIHASA_CHUNK_OVERLAP", "64"))
EMBEDDING_MODEL = os.getenv(
    "ITIHASA_EMBEDDING_MODEL", "intfloat/multilingual-e5-base"
)
EMBEDDING_BATCH_SIZE = int(os.getenv("ITIHASA_EMBEDDING_BATCH_SIZE", "32"))
OCR_DPI = 300
OCR_LANGS = os.getenv("TESSERACT_LANGS", "eng+hin+mar")
DENSE_TOP_K = 20
SPARSE_TOP_K = 20
FUSED_TOP_K = 8
RRF_K = 60
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
CORS_ORIGINS = ["http://localhost:3000"]
LOG_LEVEL = os.getenv("ITIHASA_LOG_LEVEL", "INFO").upper()
if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    raise ValueError(
        "ITIHASA_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
    )
