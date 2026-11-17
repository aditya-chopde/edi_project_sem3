import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.schemas import QueryRequest, QueryResponse
from app.services.retrieval import answer_query

router = APIRouter(prefix="/api", tags=["query"])
logger = logging.getLogger(__name__)


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest, session: Session = Depends(get_session)
) -> QueryResponse:
    logger.info("Query requested")
    try:
        response = answer_query(
            session, request.question, request.answer_language
        )
        logger.info(
            "Query completed (retrieved_chunks=%d, citations=%d)",
            len(response.retrieval.chunk_ids),
            len(response.citations),
        )
        return response
    except RuntimeError as error:
        logger.exception("Query generation failed")
        raise HTTPException(status_code=502, detail=str(error)) from error
