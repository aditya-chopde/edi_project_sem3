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
    session: Session, question: str, requested_language: str | None
) -> QueryResponse:
    language_code = (
        _language_code(requested_language)
        if requested_language
        else _detect_language(question)
    )
    language = _language_name(language_code)
    dense_ids = search_dense(question, config.DENSE_TOP_K)
    sparse_ids = search_sparse(question, config.SPARSE_TOP_K)
    fused = reciprocal_rank_fusion(
        [dense_ids, sparse_ids], top_k=config.FUSED_TOP_K
    )
    chunk_ids = [chunk_id for chunk_id, _ in fused]
    chunks = (
        list(session.exec(select(Chunk).where(Chunk.id.in_(chunk_ids))).all())
        if chunk_ids
        else []
    )
    chunks_by_id = {
        int(chunk.id): chunk for chunk in chunks if chunk.id is not None
    }
    ordered_chunks = [
        chunks_by_id[chunk_id]
        for chunk_id in chunk_ids
        if chunk_id in chunks_by_id
    ]
    documents = (
        {
            document.id: document
            for document in session.exec(
                select(Document).where(
                    Document.id.in_(
                        {chunk.document_id for chunk in ordered_chunks}
                    )
                )
            ).all()
        }
        if ordered_chunks
        else {}
    )

    diagnostics = RetrievalDiagnostics(
        dense_hits=dense_ids,
        sparse_hits=sparse_ids,
        fused=[
            FusedHit(chunk_id=chunk_id, score=score) for chunk_id, score in fused
        ],
        chunk_ids=[int(chunk.id) for chunk in ordered_chunks if chunk.id is not None],
    )
    if not ordered_chunks:
        return QueryResponse(
            answer=_NO_EVIDENCE.get(language_code, _NO_EVIDENCE["en"]),
            citations=[],
            used_chunk_ids=[],
            retrieval=diagnostics,
        )

    passages = []
    for chunk in ordered_chunks:
        document = documents.get(chunk.document_id)
        title = document.title if document else chunk.document_id
        passages.append(
            f"[chunk_db_id={chunk.id} | doc={title} | page={chunk.page_start}]\n"
            f"{chunk.text}"
        )
    generated = generate_answer(question, language, "\n\n".join(passages))
    allowed_ids = set(chunks_by_id)
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
