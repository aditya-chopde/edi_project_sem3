from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app import config
from app.database import create_db_and_tables, engine
from app.routers import api_test, documents, query
from app.schemas import HealthResponse, HomeResponse
from app.services.indexes import diagnostics_counts, load_indexes
from app.services.ingestion_queue import (
    recover_interrupted_ingestions,
    stop_ingestion_worker,
)
from app.services.indexing import stop_indexing_worker

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting Itihasa AI backend")
    config.DATASET_DIR.mkdir(parents=True, exist_ok=True)
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    config.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    create_db_and_tables()
    with Session(engine) as session:
        load_indexes(session)
    recover_interrupted_ingestions()
    dense_vectors, sparse_docs = diagnostics_counts()
    logger.info(
        "Backend ready (dense_vectors=%d, sparse_docs=%d)",
        dense_vectors,
        sparse_docs,
    )
    try:
        yield
    finally:
        stop_ingestion_worker()
        stop_indexing_worker()
        logger.info("Shutting down Itihasa AI backend")


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
app.include_router(api_test.router)


@app.get("/", response_model=HomeResponse)
def home() -> HomeResponse:
    logger.info("API home endpoint requested")
    return HomeResponse(
        status="ok",
        message="Welcome to the Itihasa AI API",
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    dense_vectors, sparse_docs = diagnostics_counts()
    logger.info(
        "Health check (dense_vectors=%d, sparse_docs=%d)",
        dense_vectors,
        sparse_docs,
    )
    return HealthResponse(
        status="ok", dense_vectors=dense_vectors, sparse_docs=sparse_docs
    )
