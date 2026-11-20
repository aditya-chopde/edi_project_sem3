import hashlib
import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import config
from app.database import engine, get_session
from app.models import Chunk, Document
from app.schemas import DocumentOut
from app.services.indexes import rebuild_all
from app.services.ingestion_queue import queue_document_ingestion

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .") or "upload"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _save_upload(file: UploadFile, path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("wb") as destination:
        while block := file.file.read(1024 * 1024):
            digest.update(block)
            destination.write(block)
    return digest.hexdigest()


def _remove_raw_directory(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return
    except OSError:
        logger.exception("Could not remove temporary upload directory %s", path)


def _find_duplicate(
    session: Session, document_id: str, content_sha256: str
) -> Document | None:
    duplicate = session.exec(
        select(Document)
        .where(Document.content_sha256 == content_sha256)
        .where(Document.id != document_id)
        .limit(1)
    ).first()
    if duplicate is not None:
        return duplicate

    legacy_documents = session.exec(
        select(Document)
        .where(Document.content_sha256.is_(None))
        .where(Document.id != document_id)
    ).all()
    known_hashes = {
        document.content_sha256: document
        for document in session.exec(
            select(Document).where(Document.content_sha256.is_not(None))
        ).all()
    }
    changed = False
    for legacy_document in legacy_documents:
        raw_path = (
            config.RAW_DIR / legacy_document.id / legacy_document.filename
        )
        try:
            legacy_hash = _hash_file(raw_path)
        except FileNotFoundError:
            logger.warning(
                "Could not backfill document hash because the raw file is missing "
                "(document_id=%s)",
                legacy_document.id,
            )
            continue
        except OSError:
            logger.exception(
                "Could not backfill document hash (document_id=%s)",
                legacy_document.id,
            )
            continue

        known_document = known_hashes.get(legacy_hash)
        if known_document is None:
            legacy_document.content_sha256 = legacy_hash
            session.add(legacy_document)
            known_hashes[legacy_hash] = legacy_document
            changed = True
            known_document = legacy_document
        if legacy_hash == content_sha256:
            duplicate = known_document

    if changed:
        session.commit()
    return duplicate


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
        logger.warning("Rejected upload with unsupported type %s", suffix or "(none)")
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {suffix or 'no extension'}",
        )

    document_id = str(uuid.uuid4())
    raw_directory = config.RAW_DIR / document_id
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
    temporary_path = raw_directory / f".{filename}.uploading"
    raw_path = raw_directory / filename
    try:
        raw_directory.mkdir(parents=True, exist_ok=True)
        content_sha256 = _save_upload(file, temporary_path)
    except OSError as error:
        document.status = "failed"
        document.error = (str(error).strip() or "Unable to save uploaded file")[:500]
        session.add(document)
        session.commit()
        _remove_raw_directory(raw_directory)
        logger.exception("Could not save uploaded document %s", document_id)
        return document

    duplicate = _find_duplicate(session, document_id, content_sha256)
    if duplicate is not None:
        session.delete(document)
        session.commit()
        existing_document_id = duplicate.id
        _remove_raw_directory(raw_directory)
        logger.info(
            "Reused existing document for identical upload "
            "(document_id=%s, existing_document_id=%s)",
            document_id,
            existing_document_id,
        )
        return duplicate

    try:
        temporary_path.replace(raw_path)
    except OSError as error:
        document.status = "failed"
        document.error = (str(error).strip() or "Unable to finalize uploaded file")[:500]
        session.add(document)
        session.commit()
        _remove_raw_directory(raw_directory)
        logger.exception("Could not finalize uploaded document %s", document_id)
        return document

    document.content_sha256 = content_sha256
    session.add(document)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        duplicate = session.exec(
            select(Document)
            .where(Document.content_sha256 == content_sha256)
            .where(Document.id != document_id)
            .limit(1)
        ).first()
        if duplicate is None:
            raise
        pending_document = session.get(Document, document_id)
        if pending_document is not None:
            session.delete(pending_document)
            session.commit()
        existing_document_id = duplicate.id
        _remove_raw_directory(raw_directory)
        logger.info(
            "Reused document created by a concurrent identical upload "
            "(document_id=%s, existing_document_id=%s)",
            document_id,
            existing_document_id,
        )
        return duplicate

    background_tasks.add_task(queue_document_ingestion, document_id, raw_path)
    logger.info(
        "Accepted document upload (document_id=%s, file_type=%s)",
        document_id,
        suffix,
    )
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(session: Session = Depends(get_session)) -> list[Document]:
    documents = list(
        session.exec(select(Document).order_by(Document.created_at.desc())).all()
    )
    logger.info("Listed documents (count=%d)", len(documents))
    return documents


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str, session: Session = Depends(get_session)
) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        logger.warning(
            "Document status requested but not found (document_id=%s)",
            document_id,
        )
        raise HTTPException(status_code=404, detail="Document not found")
    logger.info(
        "Returned document status (document_id=%s, status=%s)",
        document_id,
        document.status,
    )
    return document


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str, session: Session = Depends(get_session)
) -> None:
    document = session.get(Document, document_id)
    if document is None:
        logger.warning(
            "Delete requested for missing document (document_id=%s)",
            document_id,
        )
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
    logger.info(
        "Deleted document and rebuilt indexes (document_id=%s, chunks=%d)",
        document_id,
        len(chunks),
    )
