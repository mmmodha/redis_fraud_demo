"""FastAPI router for feature-store debug + health endpoints.

Lives in its own module so the main app stays a thin composition layer and
multiple Wave-2 agents can add routers without conflicting in ``app.main``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import features

router = APIRouter(tags=["features"])


@router.get("/health/features")
def health_features() -> dict:
    try:
        summary = features.get_store().latency_summary()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"latency": summary}


@router.get("/debug/features/{card_id}")
def debug_features(card_id: str, customer_id: str | None = None) -> dict:
    try:
        data = features.get_features(card_id, customer_id=customer_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"card_id": card_id, "customer_id": customer_id, "features": data}
