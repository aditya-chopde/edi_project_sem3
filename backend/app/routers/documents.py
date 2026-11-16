import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from app import config
from app.database import engine, get_session
from app.models import Chunk, Document
from app.schemas import DocumentOut
from app.services.indexes import rebuild_all
from app.services.ingest import ingest_document

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .") or "upload"


@router.post("/upload", response_model=DocumentOut, status_code=202)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default=None),
    historical_period: Optional[str] = Form(default=None),
    source_url: Optional[str] = Form(default=None),
    session: Session = Depends(get_session),
) -> Document:
    filename = _safe_filename(file.filename or "upload")
    suffix = Path(filename).suffix.lower()
    if suffix not in config.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {suffix or 'no extension'}",
        )

    document_id = str(uuid.uuid4())
    raw_directory = config.RAW_DIR / document_id
    raw_path = raw_directory / filename
    document = Document(
        id=document_id,
        title=(title or "").strip() or Path(filename).stem,
        filename=filename,
        file_type=suffix,
        language=(language or "").strip() or "unknown",
        historical_period=historical_period,
        source_url=source_url,
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    try:
        raw_directory.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(file.file.read())
    except OSError as error:
        document.status = "failed"
        document.error = (str(error).strip() or "Unable to save uploaded file")[:500]
        session.add(document)
        session.commit()
        return document

    background_tasks.add_task(ingest_document, document_id, raw_path)
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(session: Session = Depends(get_session)) -> list[Document]:
    return list(session.exec(select(Document).order_by(Document.created_at.desc())).all())


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str, session: Session = Depends(get_session)
) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str, session: Session = Depends(get_session)
) -> None:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = list(
        session.exec(select(Chunk).where(Chunk.document_id == document_id)).all()
    )
    for chunk in chunks:
        session.delete(chunk)
    session.delete(document)
    session.commit()
    raw_directory = config.RAW_DIR / document_id
    if raw_directory.exists():
        shutil.rmtree(raw_directory)
    (config.PROCESSED_DIR / f"doc_{document_id}_chunks.jsonl").unlink(missing_ok=True)
    with Session(engine) as index_session:
        rebuild_all(index_session)
