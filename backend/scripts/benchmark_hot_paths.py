import argparse
import os
from pathlib import Path
import statistics
import sys
import tempfile
from time import perf_counter

_temporary_dataset = tempfile.TemporaryDirectory(prefix="itihasa-benchmark-")
os.environ["ITIHASA_DATASET_DIR"] = str(
    Path(_temporary_dataset.name) / "dataset"
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import delete
from sqlmodel import Session, SQLModel, create_engine

from app.models import Chunk, Document
from app.services.indexes import _tokens


def _database_insert_timings(row_count: int, trials: int) -> dict[str, list[float]]:
    with tempfile.TemporaryDirectory(prefix="itihasa-db-benchmark-") as root:
        engine = create_engine(f"sqlite:///{Path(root) / 'benchmark.db'}")
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                Document(
                    id="benchmark",
                    title="Benchmark",
                    filename="benchmark.txt",
                    file_type=".txt",
                    language="en",
                )
            )
            session.commit()

        timings = {"refresh_each_row": [], "batch_flush": []}
        texts = [
            f"Historical document passage {index}: Maurya Gupta India evidence."
            for index in range(row_count)
        ]
        for mode in timings:
            for trial in range(trials):
                with Session(engine) as session:
                    session.exec(delete(Chunk))
                    session.commit()
                    rows = [
                        Chunk(
                            document_id="benchmark",
                            chunk_index=trial * row_count + index,
                            text=text,
                            page_start=1,
                            page_end=1,
                            language="en",
                        )
                        for index, text in enumerate(texts)
                    ]
                    started_at = perf_counter()
                    session.add_all(rows)
                    if mode == "refresh_each_row":
                        session.commit()
                        for row in rows:
                            session.refresh(row)
                    else:
                        session.flush()
                        session.commit()
                    timings[mode].append(perf_counter() - started_at)
        engine.dispose()
        return timings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Microbenchmark the database and index hot paths."
    )
    parser.add_argument("--chunks", type=int, default=3000)
    parser.add_argument("--trials", type=int, default=3)
    arguments = parser.parse_args()
    if arguments.chunks < 1 or arguments.trials < 1:
        parser.error("--chunks and --trials must be positive")

    timings = _database_insert_timings(arguments.chunks, arguments.trials)
    medians = {
        name: statistics.median(values) for name, values in timings.items()
    }
    print(f"SQLite insert timing for {arguments.chunks} chunks, seconds:")
    for name, values in timings.items():
        print(f"  {name}: {values}; median={medians[name]:.4f}")
    print(
        "  speedup: "
        f"{medians['refresh_each_row'] / medians['batch_flush']:.2f}x"
    )

    corpus = [
        _tokens(
            f"Historical document passage {index}: Maurya Gupta India evidence."
        )
        for index in range(arguments.chunks)
    ]
    started_at = perf_counter()
    BM25Okapi(corpus)
    print(f"BM25 tokenization + construction: {perf_counter() - started_at:.4f}s")

    vectors = np.random.default_rng(42).random(
        (arguments.chunks, 768), dtype=np.float32
    )
    index = faiss.IndexFlatIP(768)
    started_at = perf_counter()
    index.add(vectors)
    add_seconds = perf_counter() - started_at
    with tempfile.TemporaryDirectory(prefix="itihasa-faiss-benchmark-") as root:
        index_path = Path(root) / "benchmark.index"
        started_at = perf_counter()
        faiss.write_index(index, str(index_path))
        persist_seconds = perf_counter() - started_at
    print(
        f"FAISS add ({arguments.chunks}x768): {add_seconds:.4f}s; "
        f"persist: {persist_seconds:.4f}s"
    )


if __name__ == "__main__":
    main()
