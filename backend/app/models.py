from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


class Document(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    title: str
    filename: str
    file_type: str
    content_sha256: Optional[str] = None
    language: str
    historical_period: Optional[str] = None
    source_url: Optional[str] = None
    status: str = Field(default="pending", index=True)
    progress_percent: int = 0
    progress_detail: Optional[str] = None
    error: Optional[str] = None
    num_pages: int = 0
    num_chunks: int = 0
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
    chunks: list["Chunk"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Chunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: str = Field(foreign_key="document.id", index=True)
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    language: str
    book_number: Optional[str] = None
    parvan: Optional[int] = None
    line_id: Optional[str] = None
    line_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    section_header: Optional[str] = None
    document: Optional[Document] = Relationship(back_populates="chunks")
