from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Document(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    title: str
    filename: str
    file_type: str
    language: str
    historical_period: Optional[str] = None
    source_url: Optional[str] = None
    status: str = Field(default="pending", index=True)
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
    document: Optional[Document] = Relationship(back_populates="chunks")
