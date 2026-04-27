"""
Embeddings client for the R&D memory layer.

Reads provider/model/dimension from environment so a future swap (e.g.
to a different OpenAI-compatible endpoint) is config-only:

    EMBEDDING_PROVIDER=openai            # only 'openai' supported in v0
    EMBEDDING_MODEL=text-embedding-3-small
    EMBEDDING_DIMENSION=1536             # MUST match memory_items.embedding column

Single async entry point: embed(texts). Returns one numpy float32 vector
per input string in the same order. Numpy arrays (not Python lists) are
required so pgvector's psycopg adapter can dump them straight into the
`vector(1536)` column — db.py registers JsonbDumper for `list`, which
would otherwise hijack list[float] params and send them as jsonb.
"""

import os
from typing import Sequence

import numpy as np
from openai import AsyncOpenAI

# OpenAI's embeddings endpoint accepts up to 2048 inputs per call. We use
# a smaller batch to keep latency and per-call memory predictable; tune
# upward if ingest throughput becomes a bottleneck.
BATCH_SIZE = 100


def _config() -> tuple[str, str, int]:
    provider = os.environ.get("EMBEDDING_PROVIDER", "openai").lower()
    model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    dim = int(os.environ.get("EMBEDDING_DIMENSION", "1536"))
    if provider != "openai":
        raise RuntimeError(
            f"EMBEDDING_PROVIDER={provider!r} is not supported in v0. "
            f"Only 'openai' is wired up; add a branch here when needed."
        )
    return provider, model, dim


def _client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Required for the R&D embeddings "
            "client. Set it in the process environment before ingesting."
        )
    base_url = os.environ.get("OPENAI_BASE_URL") or None
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


async def embed(texts: Sequence[str]) -> list[np.ndarray]:
    """
    Embed `texts` and return one float32 ndarray per input, in order.

    Empty input list → empty output. Raises if any text is empty (the
    embeddings endpoint rejects empty strings; better to fail loud here
    than to get a confusing 400 back).
    """
    if not texts:
        return []
    for i, t in enumerate(texts):
        if not t or not t.strip():
            raise ValueError(f"Cannot embed empty/whitespace text at index {i}.")

    _, model, dim = _config()
    client = _client()

    out: list[np.ndarray] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = list(texts[start : start + BATCH_SIZE])
        resp = await client.embeddings.create(model=model, input=batch)
        for item in resp.data:
            vec = np.asarray(item.embedding, dtype=np.float32)
            if vec.shape != (dim,):
                raise RuntimeError(
                    f"Embedding dimension mismatch: model returned {vec.shape[0]} "
                    f"but EMBEDDING_DIMENSION={dim}. Either update the env var "
                    f"or run a re-embed migration with a new vector(N) column."
                )
            out.append(vec)
    return out
