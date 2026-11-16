from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app import config
from app.database import create_db_and_tables, engine
from app.routers import documents, query
from app.schemas import HealthResponse
from app.services.indexes import diagnostics_counts, load_indexes


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    config.DATASET_DIR.mkdir(parents=True, exist_ok=True)
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    config.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    create_db_and_tables()
    with Session(engine) as session:
        load_indexes(session)
    yield


app = FastAPI(title="Itihasa AI API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(documents.router)
app.include_router(query.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    dense_vectors, sparse_docs = diagnostics_counts()
    return HealthResponse(
        status="ok", dense_vectors=dense_vectors, sparse_docs=sparse_docs
    )
