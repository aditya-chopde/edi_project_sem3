from collections.abc import Generator

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


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
