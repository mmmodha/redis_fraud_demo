"""FastAPI app exposing the hero-transaction trigger.

The demo UI calls ``POST /trigger/{hero}`` to inject the scripted next
transaction. Listed as a separate module so the backend can either:

  * mount the ``router`` on its main FastAPI app, or
  * run this file directly as a small sidecar service via uvicorn.

Run standalone:
    uvicorn data.trigger_api:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException

from data import heroes
from data.trigger import insert_trigger

router = APIRouter(prefix="/trigger", tags=["trigger"])


@router.get("/heroes")
def list_heroes() -> dict:
    return {
        "heroes": [
            {
                "key": h.key,
                "customer_id": h.customer_id,
                "name": h.name,
                "trigger_amount": heroes.TRIGGERS[h.key].amount,
                "trigger_merchant": heroes.TRIGGERS[h.key].merchant_name,
                "trigger_country": heroes.TRIGGERS[h.key].country,
            }
            for h in heroes.HEROES.values()
        ]
    }


@router.post("/{hero}")
def trigger(hero: str) -> dict:
    if hero not in heroes.HEROES:
        raise HTTPException(status_code=404, detail=f"unknown hero '{hero}'")
    row = insert_trigger(hero)  # type: ignore[arg-type]
    return {"ok": True, "transaction": row}


app = FastAPI(title="Hero Transaction Trigger")
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
