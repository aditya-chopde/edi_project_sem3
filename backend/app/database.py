from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app import config


config.DATASET_DIR.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    f"sqlite:///{config.DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)


def create_db_and_tables() -> None:
    config.DATASET_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    document_columns = {
        column["name"] for column in inspect(engine).get_columns("document")
    }
    chunk_columns = {
        column["name"] for column in inspect(engine).get_columns("chunk")
    }
    with engine.begin() as connection:
        if "progress_percent" not in document_columns:
            connection.execute(
                text(
                    "ALTER TABLE document ADD COLUMN "
                    "progress_percent INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "progress_detail" not in document_columns:
            connection.execute(
                text("ALTER TABLE document ADD COLUMN progress_detail VARCHAR")
            )
        if "content_sha256" not in document_columns:
            connection.execute(
                text("ALTER TABLE document ADD COLUMN content_sha256 VARCHAR")
            )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_document_content_sha256 ON document(content_sha256) "
                "WHERE content_sha256 IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE document SET progress_percent = 100, "
                "progress_detail = COALESCE(progress_detail, 'Ingestion complete') "
                "WHERE status = 'indexed' AND progress_percent < 100"
            )
        )
        chunk_migrations = {
            "book_number": "VARCHAR",
            "parvan": "INTEGER",
            "line_id": "VARCHAR",
            "line_ids": "JSON NOT NULL DEFAULT '[]'",
            "section_header": "TEXT",
        }
        for column_name, column_type in chunk_migrations.items():
            if column_name not in chunk_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE chunk ADD COLUMN "
                        f"{column_name} {column_type}"
                    )
                )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunk_line_id "
                "ON chunk(line_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunk_book_number "
                "ON chunk(book_number)"
            )
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_chunk_parvan ON chunk(parvan)")
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunk_section_header "
                "ON chunk(section_header)"
            )
        )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
