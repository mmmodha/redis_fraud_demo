"""Naive RAG over the bank policy / study corpus stored in Redis.

Pipeline (no LLM):

  data/policies/*.md
        │  chunk on blank lines (~120-token chunks)
        ▼
  sentence-transformers all-MiniLM-L6-v2 → 384-d float32 vectors
        ▼
  RediSearch HNSW index `idx:policies` over keys `policy:{chunk_id}`

``PolicyRAG.search(query, k)`` runs one KNN query and returns the top-k chunks
together with a ``TraceStep`` recording the query, chunk IDs, and latency for
the IRIS / RAG side-by-side UI panels.

The embedder is dependency-injected (``embedder=`` constructor arg) so tests
can stub it out without pulling the 90 MB MiniLM model into pytest.
"""

from __future__ import annotations

import glob
import os
import re
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

import redis

from app.schemas import TraceStep


INDEX_NAME = "idx:policies"
KEY_PREFIX = "policy:"
EMBED_DIM = 384  # all-MiniLM-L6-v2
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

Embedder = Callable[[list[str]], list[list[float]]]


# ---------- chunking -------------------------------------------------------

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")


@dataclass(frozen=True)
class PolicyChunk:
    """One vector-indexable slice of a policy document."""

    chunk_id: str        # unique key suffix, e.g. "foreign-travel-002"
    doc_id: str          # source filename without extension
    title: str           # nearest preceding heading
    text: str            # chunk body (raw markdown, no leading heading line)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def chunk_markdown(path: Path, max_chars: int = 900) -> list[PolicyChunk]:
    """Split a markdown file into ~paragraph-sized chunks.

    Headings are not duplicated into the chunk body; we track the most recent
    heading and emit it as the ``title``. Adjacent short paragraphs are merged
    until the chunk reaches roughly ``max_chars`` so HNSW recall improves on
    the short bullet-list policy files.
    """
    doc_id = _slugify(path.stem)
    title = _slugify(path.stem).replace("-", " ").title()
    chunks: list[PolicyChunk] = []
    buf: list[str] = []
    current_title = title
    counter = 0

    def flush() -> None:
        nonlocal counter, buf
        text = "\n".join(buf).strip()
        if text:
            counter += 1
            chunks.append(
                PolicyChunk(
                    chunk_id=f"{doc_id}-{counter:03d}",
                    doc_id=doc_id,
                    title=current_title,
                    text=text,
                )
            )
        buf = []

    raw = path.read_text(encoding="utf-8")
    paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    for para in paras:
        m = _HEADING_RE.match(para.splitlines()[0])
        if m and len(para.splitlines()) == 1:
            flush()
            current_title = m.group(1).strip()
            continue
        candidate = "\n".join(buf + [para])
        if len(candidate) > max_chars and buf:
            flush()
            buf = [para]
        else:
            buf.append(para)
    flush()
    return chunks


def discover_policy_files(root: str | os.PathLike[str]) -> list[Path]:
    """Return all ``.md`` policy files except READMEs."""
    files = sorted(Path(p) for p in glob.glob(os.path.join(str(root), "*.md")))
    return [f for f in files if f.name.lower() != "readme.md"]


# ---------- default embedder (sentence-transformers, lazily loaded) --------

_model_cache: dict[str, object] = {}


def default_embedder(texts: list[str]) -> list[list[float]]:
    """Embed with sentence-transformers/all-MiniLM-L6-v2.

    Cached at module level so successive calls within one process reuse the
    loaded model. Importing ``sentence_transformers`` is deferred so unit
    tests that inject a stub embedder don't need the package installed.
    """
    model = _model_cache.get(EMBED_MODEL_NAME)
    if model is None:
        from sentence_transformers import SentenceTransformer  # local import

        model = SentenceTransformer(EMBED_MODEL_NAME)
        _model_cache[EMBED_MODEL_NAME] = model
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return [vec.astype("float32").tolist() for vec in vectors]


def _to_blob(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


# ---------- index lifecycle ------------------------------------------------

def _drop_index(client: redis.Redis) -> None:
    try:
        client.execute_command("FT.DROPINDEX", INDEX_NAME, "DD")
    except redis.ResponseError as exc:
        # Unknown index is fine on first run.
        if "unknown index" not in str(exc).lower() and "no such index" not in str(exc).lower():
            raise


def _create_index(client: redis.Redis) -> None:
    client.execute_command(
        "FT.CREATE", INDEX_NAME,
        "ON", "HASH", "PREFIX", "1", KEY_PREFIX,
        "SCHEMA",
        "doc_id", "TAG",
        "title", "TEXT",
        "text", "TEXT",
        "embedding", "VECTOR", "HNSW", "6",
        "TYPE", "FLOAT32",
        "DIM", str(EMBED_DIM),
        "DISTANCE_METRIC", "COSINE",
    )


def build_index(
    client: redis.Redis,
    policy_dir: str | os.PathLike[str],
    embedder: Optional[Embedder] = None,
) -> dict:
    """Drop + rebuild ``idx:policies`` end-to-end. Idempotent.

    Returns ``{"docs": N, "chunks": M}`` for ``make policy-index`` output.
    """
    emb = embedder or default_embedder
    files = discover_policy_files(policy_dir)
    all_chunks: list[PolicyChunk] = []
    for f in files:
        all_chunks.extend(chunk_markdown(f))

    _drop_index(client)
    _create_index(client)

    if not all_chunks:
        return {"docs": 0, "chunks": 0}

    vectors = emb([c.text for c in all_chunks])
    pipe = client.pipeline(transaction=False)
    for chunk, vec in zip(all_chunks, vectors):
        pipe.hset(
            f"{KEY_PREFIX}{chunk.chunk_id}",
            mapping={
                "doc_id": chunk.doc_id,
                "title": chunk.title,
                "text": chunk.text,
                "embedding": _to_blob(vec),
            },
        )
    pipe.execute()
    return {"docs": len(files), "chunks": len(all_chunks)}


# ---------- search ---------------------------------------------------------

class PolicyRAG:
    """Read-side wrapper used by ``/chat/naive-rag`` and the
    ``search_policy`` agent tool. Holds its own embedder + Redis client."""

    def __init__(
        self,
        client: redis.Redis,
        embedder: Optional[Embedder] = None,
    ) -> None:
        self._client = client
        self._embedder = embedder or default_embedder

    @classmethod
    def from_env(cls, embedder: Optional[Embedder] = None) -> "PolicyRAG":
        url = os.environ.get("REDIS_URL", "")
        if not url:
            raise RuntimeError("REDIS_URL is not set")
        client = redis.Redis.from_url(
            url, decode_responses=False,
            socket_timeout=5, socket_connect_timeout=5,
        )
        return cls(client, embedder=embedder)

    def search(self, query: str, k: int = 5) -> tuple[list[dict], TraceStep]:
        """Return ``(chunks, trace)`` for the IRIS / RAG UI panel.

        ``chunks`` is a list of ``{chunk_id, doc_id, title, text, score}``
        sorted by ascending cosine distance (best first).
        """
        start = time.perf_counter()
        vec = self._embedder([query])[0]
        blob = _to_blob(vec)
        try:
            raw = self._client.execute_command(
                "FT.SEARCH", INDEX_NAME,
                f"*=>[KNN {k} @embedding $vec AS score]",
                "PARAMS", "2", "vec", blob,
                "RETURN", "4", "doc_id", "title", "text", "score",
                "SORTBY", "score",
                "DIALECT", "2",
                "LIMIT", "0", str(k),
            )
        except redis.ResponseError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            trace = TraceStep(
                component="policy_rag", tool="search_policy",
                input={"query": query, "k": k},
                output_summary=f"index error: {exc}",
                output_data={"error": str(exc)},
                latency_ms=latency_ms, redis_keys_touched=[INDEX_NAME],
            )
            return [], trace

        chunks = _parse_ft_search(raw)
        latency_ms = int((time.perf_counter() - start) * 1000)
        trace = TraceStep(
            component="policy_rag", tool="search_policy",
            input={"query": query, "k": k},
            output_summary=f"{len(chunks)} chunk(s): "
                           + ", ".join(c["chunk_id"] for c in chunks[:3])
                           + ("…" if len(chunks) > 3 else ""),
            output_data={"chunks": chunks},
            latency_ms=latency_ms,
            redis_keys_touched=[INDEX_NAME] + [f"{KEY_PREFIX}{c['chunk_id']}" for c in chunks],
        )
        return chunks, trace


def _parse_ft_search(raw: list) -> list[dict]:
    """Convert FT.SEARCH reply into a list of dicts. Result shape:
    ``[count, key1, [field1, value1, ...], key2, [...]]`` (bytes)."""
    out: list[dict] = []
    if not raw or len(raw) < 2:
        return out
    iter_raw: Iterable = raw[1:]
    pairs = list(iter_raw)
    for i in range(0, len(pairs), 2):
        key = pairs[i]
        fields = pairs[i + 1] if i + 1 < len(pairs) else []
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        chunk_id = key.removeprefix(KEY_PREFIX) if key.startswith(KEY_PREFIX) else key
        record = {"chunk_id": chunk_id}
        for j in range(0, len(fields), 2):
            fname = fields[j]
            fval = fields[j + 1] if j + 1 < len(fields) else b""
            if isinstance(fname, bytes):
                fname = fname.decode("utf-8")
            if isinstance(fval, bytes):
                try:
                    fval = fval.decode("utf-8")
                except UnicodeDecodeError:
                    fval = fval.hex()
            if fname == "score":
                try:
                    fval = float(fval)
                except (TypeError, ValueError):
                    pass
            record[fname] = fval
        out.append(record)
    return out


__all__ = [
    "PolicyRAG",
    "PolicyChunk",
    "build_index",
    "chunk_markdown",
    "discover_policy_files",
    "default_embedder",
    "INDEX_NAME",
    "KEY_PREFIX",
    "EMBED_DIM",
    "EMBED_MODEL_NAME",
]
