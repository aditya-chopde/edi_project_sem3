from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


DocumentStatus = Literal[
    "pending", "extracting", "chunking", "embedding", "indexed", "failed"
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
    error: Optional[str]
    num_pages: int
    num_chunks: int
    created_at: datetime


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    answer_language: Optional[str] = Field(default=None, max_length=64)


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
