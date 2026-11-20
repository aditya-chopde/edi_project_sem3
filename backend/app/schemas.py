from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


DocumentStatus = Literal[
    "pending",
    "extracting",
    "chunking",
    "embedding",
    "indexing",
    "indexed",
    "failed",
]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    filename: str
    file_type: str
    language: str
    historical_period: Optional[str]
    source_url: Optional[str]
    status: DocumentStatus
    progress_percent: int
    progress_detail: Optional[str]
    error: Optional[str]
    num_pages: int
    num_chunks: int
    created_at: datetime


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    answer_language: Optional[str] = Field(default=None, max_length=64)
    book_number: Optional[str] = Field(default=None, pattern=r"^\d{2}$")
    parvan: Optional[int] = Field(default=None, ge=0, le=99)
    line_id: Optional[str] = Field(default=None, pattern=r"^\d{8}[A-Za-z]$")
    section_header: Optional[str] = Field(default=None, max_length=256)


class Citation(BaseModel):
    document_id: str
    title: str
    page_start: int
    page_end: int
    excerpt: str


class FusedHit(BaseModel):
    chunk_id: int
    score: float


class RetrievalDiagnostics(BaseModel):
    dense_hits: list[int]
    sparse_hits: list[int]
    fused: list[FusedHit]
    reranked: list[FusedHit]
    chunk_ids: list[int]


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    used_chunk_ids: list[int]
    retrieval: RetrievalDiagnostics


class HealthResponse(BaseModel):
    status: str
    dense_vectors: int
    sparse_docs: int

class HomeResponse(BaseModel):
    status: str
    message: str
