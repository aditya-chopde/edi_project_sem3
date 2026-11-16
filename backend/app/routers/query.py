from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.schemas import QueryRequest, QueryResponse
from app.services.retrieval import answer_query

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest, session: Session = Depends(get_session)
) -> QueryResponse:
    try:
        return answer_query(session, request.question, request.answer_language)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
