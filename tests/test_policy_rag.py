"""End-to-end tests for the naive RAG pipeline.

Runs against the live Redis Cloud database (REDIS_URL) because we need
RediSearch HNSW which fakeredis doesn't fully implement. The tests use a
deterministic bag-of-words embedder so we don't have to pull the
sentence-transformers model (90 MB) into CI. The embedder is good enough
to demonstrate that lexically related queries rank related chunks high,
which is what the assertions check.

Skips cleanly if REDIS_URL is not set so a fresh checkout doesn't fail.
"""

from __future__ import annotations

import os
import re
import sys
from hashlib import blake2b
from pathlib import Path

import pytest

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if not REDIS_URL:
    pytest.skip("REDIS_URL not set — skipping naive-RAG integration tests.",
                allow_module_level=True)

import redis  # noqa: E402

from app.policy_rag import (  # noqa: E402
    EMBED_DIM, INDEX_NAME, KEY_PREFIX,
    PolicyRAG, build_index, chunk_markdown, discover_policy_files,
)


# ---------- deterministic stub embedder ------------------------------------

_TOKEN_RE = re.compile(r"[a-z]{3,}")


def bag_of_words_embedder(texts: list[str]) -> list[list[float]]:
    """Project each text into a fixed-size float32 vector via hashed token bag.

    Each token contributes ``+1`` to the dimension ``hash(token) % EMBED_DIM``;
    the vector is then L2-normalised. Lexically overlapping texts get
    high cosine similarity — enough signal for the RAG assertions below.
    """
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * EMBED_DIM
        for tok in _TOKEN_RE.findall(text.lower()):
            h = blake2b(tok.encode("utf-8"), digest_size=2).digest()
            idx = int.from_bytes(h, "big") % EMBED_DIM
            vec[idx] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        vectors.append(vec)
    return vectors


# ---------- fixtures -------------------------------------------------------

POLICY_DIR = Path(__file__).resolve().parent.parent / "data" / "policies"
TEST_KEY_PREFIX = "test:policy:"
TEST_INDEX_NAME = "test:idx:policies"


@pytest.fixture(scope="module")
def client():
    c = redis.Redis.from_url(REDIS_URL, decode_responses=False,
                             socket_timeout=10, socket_connect_timeout=10)
    c.ping()
    yield c
    # Clean up after the module — drop the test index + delete the test docs.
    try:
        c.execute_command("FT.DROPINDEX", TEST_INDEX_NAME, "DD")
    except redis.ResponseError:
        pass


@pytest.fixture(scope="module")
def built_index(client, monkeypatch_module):
    """Build the policy index under a TEST-prefixed key + index name so we
    don't clobber the canonical ``idx:policies`` while tests run."""
    # Rebuild against the test index by monkeypatching the module-level
    # constants for the duration of the build.
    from app import policy_rag as pr
    monkeypatch_module.setattr(pr, "INDEX_NAME", TEST_INDEX_NAME)
    monkeypatch_module.setattr(pr, "KEY_PREFIX", TEST_KEY_PREFIX)
    stats = build_index(client, POLICY_DIR, embedder=bag_of_words_embedder)
    return stats


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped monkeypatch (the built-in is function-scoped)."""
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def rag(client, built_index, monkeypatch_module):
    return PolicyRAG(client, embedder=bag_of_words_embedder)


# ---------- chunking -------------------------------------------------------

def test_discover_policy_files_finds_markdown_excluding_readme():
    files = discover_policy_files(POLICY_DIR)
    names = {f.name for f in files}
    assert "01-fraud-policy-overview.md" in names
    assert "README.md" not in names
    assert len(files) >= 10


def test_chunk_markdown_produces_titled_chunks():
    chunks = chunk_markdown(POLICY_DIR / "02-fraud-policy-foreign-travel.md")
    assert len(chunks) >= 3
    assert all(c.chunk_id.startswith("02-fraud-policy-foreign-travel-") for c in chunks)
    assert all(c.text and c.title for c in chunks)


# ---------- index lifecycle ------------------------------------------------

def test_build_index_reports_doc_and_chunk_counts(built_index):
    assert built_index["docs"] >= 10
    assert built_index["chunks"] >= built_index["docs"]


def test_build_index_is_idempotent(client, monkeypatch_module):
    """Second run drops + rebuilds cleanly; key count converges."""
    from app import policy_rag as pr  # already monkeypatched by the fixture
    first = build_index(client, POLICY_DIR, embedder=bag_of_words_embedder)
    second = build_index(client, POLICY_DIR, embedder=bag_of_words_embedder)
    assert first == second
    # Index must exist after a rebuild.
    info = client.execute_command("FT.INFO", pr.INDEX_NAME)
    assert info is not None


# ---------- retrieval ------------------------------------------------------

@pytest.mark.parametrize("query,expected_keyword", [
    ("cross-border travel", "travel"),
    ("new device first seen", "device"),
    ("high-value mcc electronics", "category"),
])
def test_search_returns_relevant_chunks(rag, query, expected_keyword):
    chunks, step = rag.search(query, k=5)
    assert step.component == "policy_rag"
    assert step.tool == "search_policy"
    assert step.latency_ms >= 0
    assert len(chunks) >= 3, f"only {len(chunks)} chunk(s) returned for {query!r}"
    # At least one of the top-5 must mention the expected keyword in title or text.
    blob = " ".join((c.get("title", "") + " " + c.get("text", "")).lower() for c in chunks)
    assert expected_keyword in blob, (
        f"none of the top-5 chunks for {query!r} mention {expected_keyword!r}"
    )


def test_search_trace_records_redis_keys(rag):
    chunks, step = rag.search("velocity threshold", k=3)
    assert step.redis_keys_touched[0].startswith("test:idx:") or \
           step.redis_keys_touched[0] == INDEX_NAME
    # Every chunk's key is recorded for the Redis Insight side-by-side moment.
    assert len(step.redis_keys_touched) == 1 + len(chunks)


def test_search_returns_empty_trace_on_missing_index(client, monkeypatch):
    """If the index doesn't exist, search must return [] plus a trace marking
    the error, not raise."""
    from app import policy_rag as pr
    monkeypatch.setattr(pr, "INDEX_NAME", "test:idx:does_not_exist")
    rag = PolicyRAG(client, embedder=bag_of_words_embedder)
    chunks, step = rag.search("anything", k=3)
    assert chunks == []
    assert "error" in step.output_summary.lower() or step.output_data.get("error")
