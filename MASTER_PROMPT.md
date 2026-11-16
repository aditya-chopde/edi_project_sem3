# MASTER PROMPT — Itihasa AI Backend (Cross-Lingual RAG for Indian Historical Documents)

## ROLE
You are a senior RAG engineer. Build the complete backend for "Itihasa AI", a cross-lingual
retrieval-augmented generation system over Indian historical documents (English, Hindi, Marathi
first). Users upload historical documents of any common file type through the UI; the system
ingests them automatically and answers historical questions in the user's language with
source-level page citations. Produce production-quality, fully working code — no placeholders,
no TODOs in critical paths.

## HARD STRUCTURE CONSTRAINT (non-negotiable)
The project root contains exactly two folders: `frontend/` (Next.js, build separately later)
and `backend/` (this is what you build). ALL data — raw uploads, extracted chunks, vector
indexes, and the database — MUST live inside `backend/dataset/`:

```
Itihasa_AI/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, lifespan (init DB + load indexes)
│   │   ├── config.py            # ALL paths + hyperparameters in one place
│   │   ├── database.py          # SQLModel/SQLite engine + session
│   │   ├── models.py            # Document + Chunk tables
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── documents.py     # upload / list / status / delete
│   │   │   └── query.py         # POST /api/query
│   │   └── services/
│   │       ├── extraction.py    # per-type text extractors, page-aware
│   │       ├── chunking.py      # page-aligned chunker
│   │       ├── embeddings.py    # multilingual-e5 with query:/passage: prefixes
│   │       ├── indexes.py       # FAISS + BM25 + RRF, persisted to disk
│   │       ├── ingest.py        # end-to-end background ingestion pipeline
│   │       ├── retrieval.py     # hybrid retrieval orchestration
│   │       └── llm.py           # Gemini answer generation + citation validation
│   ├── dataset/                 # created at runtime; everything data lives here
│   │   ├── raw/<doc_id>/        # original uploaded files
│   │   ├── processed/           # doc_<id>_chunks.jsonl chunk exports
│   │   ├── index/               # faiss.index, bm25.pkl, faiss_meta.pkl
│   │   └── itihasa.db           # SQLite
│   └── requirements.txt
└── frontend/                    # do not build; just respect this layout
```

config.py must derive `DATASET_DIR = BACKEND_DIR / "dataset"` (env-overridable) and define
RAW_DIR, PROCESSED_DIR, INDEX_DIR, DB_PATH from it. Never hardcode data paths elsewhere —
always reference `config.*`.

## TECH STACK (pinned)
Python 3.11+ · FastAPI + uvicorn · SQLModel (SQLite) · PyMuPDF · pytesseract + Pillow +
opencv-python-headless · sentence-transformers (`intfloat/multilingual-e5-base`) · faiss-cpu ·
rank_bm25 · langdetect · google-genai · python-docx · ebooklib.

## INGESTION PIPELINE (triggered by UI upload)
1. `POST /api/documents/upload` (multipart: file; optional form fields title, language,
   historical_period, source_url). Reject unsupported suffixes with 415.
   Supported: .pdf .png .jpg .jpeg .tiff .tif .bmp .txt .md .docx .epub.
2. Create Document row (status=pending), save raw bytes to `dataset/raw/<doc_id>/`.
3. Run ingestion as a FastAPI BackgroundTask with status progression, committed at every
   step so the UI can poll `GET /api/documents/{id}`:
   - extracting → extract text WITH PAGE NUMBERS (list of {page, text} blocks):
     * PDF: PyMuPDF text layer per page; if a page yields <50 chars, render at 300 dpi and
       OCR it with Tesseract (langs from env TESSERACT_LANGS, default "eng+hin+mar").
     * Images: Tesseract directly (leave an OpenCV preprocessing hook).
     * txt/md: read as one block. docx: python-docx. epub: ebooklib, strip HTML tags.
   - chunking → per-page recursive character chunking (512 chars, 64 overlap). A chunk
     must never span two pages; store page_start=page_end=page on every chunk. Delete any
     previous chunks of this document first.
   - embedding → encode chunks with `passage: ` prefix, normalized.
   - Persist chunks to the DB AND export `dataset/processed/doc_<id>_chunks.jsonl`
     (one JSON object per chunk: chunk_db_id, document_id, chunk_index, text, page_start,
     page_end, language).
   - indexed → add vectors to FAISS (IndexFlatIP, cosine via normalization), rebuild BM25
     from the DB, persist both under `dataset/index/`.
   - On ANY exception: status=failed, store the error message (truncated to 500 chars).

## RETRIEVAL + ANSWER PIPELINE (`POST /api/query` {question, answer_language?})
1. Detect query language (langdetect, or use answer_language if provided).
2. Embed the question with `query: ` prefix.
3. Dense search: FAISS top-20. Sparse search: BM25 top-20.
4. Fuse with Reciprocal Rank Fusion: score(d) = Σ 1/(k + rank_r(d)), k=60 → top-8 chunks.
5. Build a context string where every passage is annotated with
   `[chunk_db_id=<id> | doc=<title> | page=<n>]`.
6. Call Gemini (model from env GEMINI_MODEL, default "gemini-2.5-flash") with
   response_mime_type=application/json and this system prompt:
   "You are an Indian historical information assistant. Answer using only the provided
   historical evidence. Answer in the user's selected language. Do not invent facts, dates
   or events. If the context is insufficient, say the answer cannot be verified. Cite
   supporting evidence using the chunk_db_id values. Preserve historical names. If sources
   disagree, explain the disagreement. Return STRICT JSON:
   {answer, citations:[{chunk_db_id, claim}]}"
7. VALIDATE citations server-side: silently drop any chunk_db_id the model cited that was
   not in the retrieved set. The LLM must never be able to invent page numbers.
8. Respond {answer, citations:[{document_id, title, page_start, page_end, excerpt}],
   used_chunk_ids, retrieval:{dense_hits, sparse_hits, fused, chunk_ids}} — the retrieval
   diagnostics are required for offline evaluation.
9. If nothing is retrieved, return a clear "no evidence found" message in the answer
   language rather than calling the LLM.

## API SURFACE
- POST /api/documents/upload → DocumentOut (starts background ingestion)
- GET  /api/documents → list, newest first
- GET  /api/documents/{id} → DocumentOut incl. status + error (UI polling)
- DELETE /api/documents/{id} → delete chunks + raw file, rebuild BM25
- POST /api/query → QueryResponse
- GET  /health → {status, dense_vectors, sparse_docs}

## DATA MODEL
Document(id, title, filename, file_type, language, historical_period, source_url,
         status[pending|extracting|chunking|embedding|indexed|failed], error, num_pages,
         num_chunks, created_at)
Chunk(id, document_id [indexed], chunk_index, text, page_start, page_end, language)

## SECURITY / CONFIG
- Gemini API key read ONLY from env GEMINI_API_KEY; never hardcode, never expose to frontend.
- CORS restricted to http://localhost:3000.
- requirements.txt must pin minimum versions and include python-multipart.

## ACCEPTANCE CRITERIA
1. `cd backend && uvicorn app.main:app --reload` starts; /docs works.
2. Uploading a scanned PDF and a plain .txt via /docs both reach status=indexed; the UI can
   poll status; chunks appear in itihasa.db AND dataset/processed/*.jsonl; FAISS count on
   /health increases.
3. POST /api/query with a Marathi question retrieves evidence from an English document and
   returns an answer in Marathi with correct title + page citations; citation chunk ids
   all exist in the retrieved set.
4. A corrupt/unsupported file surfaces status=failed with a readable error.
5. Every data artifact is under backend/dataset/ — nothing outside it.

## OUT OF SCOPE (do not build)
Auth, Celery/queues, custom OCR models, knowledge graphs, additional languages beyond the
three, frontend code.
