"""Shared Postgres connection helper for the data module."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PgConnection


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "bank")
    password = os.environ.get("POSTGRES_PASSWORD", "bank")
    db = os.environ.get("POSTGRES_DB", "bank")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def connect() -> PgConnection:
    return psycopg2.connect(database_url())


@contextmanager
def cursor() -> Iterator[tuple]:
    conn = connect()
    try:
        cur = conn.cursor()
        try:
            yield conn, cur
            conn.commit()
        finally:
            cur.close()
    finally:
        conn.close()
