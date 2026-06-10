import os

import psycopg
import redis
from fastapi import FastAPI, HTTPException

from app import features
from app.rdi import router as rdi_router

app = FastAPI(title="Fraud Command Center API")
app.include_router(rdi_router)


def _check_redis() -> str:
    url = os.environ.get("REDIS_URL", "")
    if not url:
        return "missing REDIS_URL"
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


def _check_postgres() -> str:
    dsn = (
        f"host={os.environ.get('POSTGRES_HOST', 'postgres')} "
        f"port={os.environ.get('POSTGRES_PORT', '5432')} "
        f"dbname={os.environ.get('POSTGRES_DB', 'bank')} "
        f"user={os.environ.get('POSTGRES_USER', 'bank')} "
        f"password={os.environ.get('POSTGRES_PASSWORD', 'bank')} "
        f"connect_timeout=2"
    )
    try:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


@app.get("/health")
def health() -> dict[str, str]:
    return {"redis": _check_redis(), "postgres": _check_postgres()}


@app.get("/health/features")
def health_features() -> dict:
    try:
        summary = features.get_store().latency_summary()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"latency": summary}


@app.get("/debug/features/{card_id}")
def debug_features(card_id: str) -> dict:
    try:
        data = features.get_features(card_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"card_id": card_id, "features": data}
