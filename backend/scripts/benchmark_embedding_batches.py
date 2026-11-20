import argparse
import statistics
from pathlib import Path
import sys
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config
from app.services.embeddings import embed_passages


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark SentenceTransformer CPU embedding batch sizes."
    )
    parser.add_argument("--passages", type=int, default=64)
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[16, 32, 64])
    arguments = parser.parse_args()
    if arguments.passages < 1 or arguments.trials < 1:
        parser.error("--passages and --trials must be positive")
    if any(batch_size < 1 for batch_size in arguments.batch_sizes):
        parser.error("batch sizes must be positive")

    texts = [
        f"Historical archive passage {index}: evidence, chronology, and records in India."
        for index in range(arguments.passages)
    ]
    embed_passages(texts[: min(2, len(texts))])

    for batch_size in arguments.batch_sizes:
        config.EMBEDDING_BATCH_SIZE = batch_size
        samples = []
        for _ in range(arguments.trials):
            started_at = perf_counter()
            vectors = embed_passages(texts)
            samples.append(perf_counter() - started_at)
            if vectors.shape[0] != len(texts):
                raise RuntimeError("Embedding count does not match passage count")
            norms = np.linalg.norm(vectors, axis=1)
            if not np.allclose(norms, 1.0, atol=1e-4):
                raise RuntimeError("Passage embeddings are not normalized")
        print(
            f"batch_size={batch_size}: trials={samples}, "
            f"median_seconds={statistics.median(samples):.3f}"
        )


if __name__ == "__main__":
    main()
