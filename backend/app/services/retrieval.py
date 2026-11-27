from langdetect import DetectorFactory, LangDetectException, detect
from sqlmodel import Session, select

from app import config
from app.models import Chunk, Document
from app.schemas import Citation, FusedHit, QueryResponse, RetrievalDiagnostics
from app.services.indexes import (
    reciprocal_rank_fusion,
    search_dense,
    search_sparse,
)
from app.services.llm import generate_answer
from app.services.reranking import rerank

DetectorFactory.seed = 0

_NO_EVIDENCE = {
    "en": "No historical evidence was found for this question.",
    "hi": "इस प्रश्न के लिए कोई ऐतिहासिक साक्ष्य नहीं मिला।",
    "mr": "या प्रश्नासाठी कोणताही ऐतिहासिक पुरावा सापडला नाही.",
}


def _language_name(language_code: str) -> str:
    names = {
        "en": "English",
        "hi": "Hindi",
        "mr": "Marathi",
    }
    normalized = language_code.strip().lower()
    if normalized in names:
        return names[normalized]
    return language_code


def _language_code(language: str) -> str:
    normalized = language.strip().lower()
    aliases = {
        "english": "en",
        "hindi": "hi",
        "marathi": "mr",
    }
    if normalized in aliases:
        return aliases[normalized]
    return normalized.split("-", maxsplit=1)[0]


def _detect_language(question: str) -> str:
    try:
        detected = detect(question)
        return detected if detected in {"en", "hi", "mr"} else "en"
    except LangDetectException:
        return "en"


def answer_query(
    session: Session,
    question: str,
    requested_language: str | None,
    *,
    book_number: str | None = None,
    parvan: int | None = None,
    line_id: str | None = None,
    section_header: str | None = None,
) -> QueryResponse:
    language_code = (
        _language_code(requested_language)
        if requested_language
        else _detect_language(question)
    )
    language = _language_name(language_code)
    has_filters = any(
        value is not None
        for value in (book_number, parvan, line_id, section_header)
    )
    allowed_ids: set[int] | None = None
    if has_filters:
        statement = select(Chunk)
        if book_number is not None:
            statement = statement.where(Chunk.book_number == book_number)
        if parvan is not None:
            statement = statement.where(Chunk.parvan == parvan)
        if line_id is not None:
            statement = statement.where(Chunk.line_id == line_id)
        if section_header is not None:
            statement = statement.where(Chunk.section_header == section_header)
        allowed_ids = {
            int(chunk.id)
            for chunk in session.exec(statement).all()
            if chunk.id is not None
        }
    dense_ids = search_dense(question, config.DENSE_TOP_K, allowed_ids)
    sparse_ids = search_sparse(question, config.SPARSE_TOP_K, allowed_ids)
    fused = reciprocal_rank_fusion(
        [dense_ids, sparse_ids], top_k=config.FUSED_TOP_K
    )
    fused_ids = [chunk_id for chunk_id, _ in fused]
    chunks = (
        list(session.exec(select(Chunk).where(Chunk.id.in_(fused_ids))).all())
        if fused_ids
        else []
    )
    chunks_by_id = {
        int(chunk.id): chunk for chunk in chunks if chunk.id is not None
    }
    fused_chunks = [
        chunks_by_id[chunk_id]
        for chunk_id in fused_ids
        if chunk_id in chunks_by_id
    ]
    reranked = rerank(
        question,
        fused_chunks,
        top_k=config.RERANKED_TOP_K,
    )
    context_ids = [chunk_id for chunk_id, _ in reranked]
    context_chunks = [chunks_by_id[chunk_id] for chunk_id in context_ids]
    documents = (
        {
            document.id: document
            for document in session.exec(
                select(Document).where(
                    Document.id.in_(
                        {chunk.document_id for chunk in context_chunks}
                    )
                )
            ).all()
        }
        if context_chunks
        else {}
    )

    diagnostics = RetrievalDiagnostics(
        dense_hits=dense_ids,
        sparse_hits=sparse_ids,
        fused=[
            FusedHit(chunk_id=chunk_id, score=score) for chunk_id, score in fused
        ],
        reranked=[
            FusedHit(chunk_id=chunk_id, score=score)
            for chunk_id, score in reranked
        ],
        chunk_ids=context_ids,
    )
    if not context_chunks:
        return QueryResponse(
            answer=_NO_EVIDENCE.get(language_code, _NO_EVIDENCE["en"]),
            citations=[],
            used_chunk_ids=[],
            retrieval=diagnostics,
        )

    passages = []
    for chunk in context_chunks:
        document = documents.get(chunk.document_id)
        title = document.title if document else chunk.document_id
        passages.append(
            f"[chunk_db_id={chunk.id} | doc={title} | page={chunk.page_start}]\n"
            f"{chunk.text}"
        )
    generated = generate_answer(question, language, "\n\n".join(passages))
    allowed_ids = set(context_ids)
    used_ids = list(
        dict.fromkeys(
            chunk_id
            for chunk_id in generated.cited_chunk_ids
            if chunk_id in allowed_ids
        )
    )

    citations = []
    for chunk_id in used_ids:
        chunk = chunks_by_id[chunk_id]
        document = documents.get(chunk.document_id)
        if document is None:
            continue
        citations.append(
            Citation(
                chunk_db_id=chunk_id,
                document_id=document.id,
                title=document.title,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                excerpt=chunk.text[:500],
            )
        )
    return QueryResponse(
        answer=generated.answer,
        citations=citations,
        used_chunk_ids=used_ids,
        retrieval=diagnostics,
    )
