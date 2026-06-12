"""Chatbot endpoints — the side-by-side IRIS-vs-RAG moment.

* ``POST /chat/context-surface`` — customer-scoped agent that calls
  Context Retriever / Feature Store / Agent Memory tools as the keyword
  routing in the message suggests, then composes a templated answer.

* ``POST /chat/naive-rag`` — same request/response shape; uses ONLY policy
  document retrieval. Deliberately can't answer customer-specific questions.

Both endpoints share the ``ChatRequest`` / ``ChatResponse`` schemas in
``app.schemas`` — the UI calls them with identical bodies and renders the
two responses side-by-side.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Agent, get_agent
from app.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/context-surface", response_model=ChatResponse)
async def chat_context_surface(
    req: ChatRequest,
    agent: Agent = Depends(get_agent),
) -> ChatResponse:
    if not req.customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required")
    try:
        return await agent.chat_context_surface(
            customer_id=req.customer_id,
            message=req.message,
            history=req.history,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/naive-rag", response_model=ChatResponse)
async def chat_naive_rag(
    req: ChatRequest,
    agent: Agent = Depends(get_agent),
) -> ChatResponse:
    # customer_id is accepted to keep the request shape identical to
    # /chat/context-surface, but is deliberately not used for retrieval.
    try:
        return await agent.chat_naive_rag(
            customer_id=req.customer_id,
            message=req.message,
            history=req.history,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
