"""Deterministic verdict-fast rule engine.

Wave 7f+ split: the LLM-narrated reason on ``/agent/score`` is great for the
trace panel but too slow to drive the on-stage verdict chip. This module
ingests the same Redis-backed signals the Claude agent consumes (pending
review staging record, customer agent memory, device-history side channels)
and emits ``{verdict, confidence, signals}`` in well under 300 ms.

The verdict produced for the three hero customers must agree with
``/agent/score`` on the canonical demo run:

    Mike  → approve  (no pending review / clean baseline)
    Jane  → approve  (foreign tx + declared travel window matches country)
    Alex  → block    (first-seen device + foreign tx + no travel window)

Inputs are plain dicts so the engine is trivially unit-testable without
Redis. ``evaluate_verdict_fast`` is the only public function; the endpoint
handler wires it up to the real backends via ``call_tool``.
"""

from __future__ import annotations

from typing import Any, Optional


# Common destination-name → ISO country-code mapping for matching declared
# travel windows (stored as place names in agent memory) against the
# merchant country (stored as ISO-2). Kept tiny — extend as new heroes land.
_DESTINATION_TO_COUNTRY: dict[str, str] = {
    "singapore": "SG",
    "japan": "JP",
    "tokyo": "JP",
    "united kingdom": "GB",
    "uk": "GB",
    "london": "GB",
    "france": "FR",
    "paris": "FR",
    "brazil": "BR",
    "são paulo": "BR",
    "sao paulo": "BR",
    "united states": "US",
    "usa": "US",
    "us": "US",
}


def _destination_matches(destination: str, country_code: Optional[str]) -> bool:
    if not destination or not country_code:
        return False
    norm = destination.strip().lower()
    if _DESTINATION_TO_COUNTRY.get(norm) == country_code.upper():
        return True
    return norm == country_code.strip().lower()


def _matching_travel_window(
    memory: Optional[dict[str, Any]],
    merchant_country: Optional[str],
) -> Optional[dict[str, Any]]:
    if not memory or not merchant_country:
        return None
    windows = memory.get("travel_windows") or []
    for w in windows:
        dests = w.get("destinations") or []
        if any(_destination_matches(str(d), merchant_country) for d in dests):
            return w
    return None


def evaluate_verdict_fast(
    *,
    customer_id: str,
    pending_review: Optional[dict[str, Any]],
    memory: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return ``{verdict, confidence, signals}`` for a customer.

    ``pending_review`` is the JSON staged at ``pending_review:{customer_id}``
    or ``None`` when no transaction is queued. ``memory`` is the agent-memory
    document at ``mem:{customer_id}`` (or ``None``).
    """

    signals: list[str] = []

    # No in-flight transaction → nothing to block. Highest confidence on the
    # baseline path because we are reading authoritative Redis state.
    if not pending_review:
        signals.append("no_pending_review")
        return {"verdict": "approve", "confidence": 0.92, "signals": signals}

    pr = pending_review
    merchant_country = pr.get("merchant_country")
    foreign_country = bool(pr.get("foreign_country"))
    impossible_travel = bool(pr.get("impossible_travel"))
    device_first_seen_today = bool(pr.get("device_first_seen_today"))
    device_id = pr.get("device_id")

    if device_first_seen_today:
        signals.append(
            f"first_seen_device:{device_id or 'unknown'}({merchant_country or '??'})"
        )
    if impossible_travel:
        signals.append("impossible_travel_velocity:high")
    if foreign_country:
        signals.append(f"foreign_country:{merchant_country or '??'}")

    matching_window = _matching_travel_window(memory, merchant_country)
    if matching_window:
        signals.append(
            f"declared_travel_window_matches_merchant_country:{merchant_country}"
        )

    # Hard-block paths: first-seen device on a foreign tx with no declared
    # travel, or impossible-travel velocity with no declared travel.
    if device_first_seen_today and foreign_country and not matching_window:
        return {"verdict": "block", "confidence": 0.94, "signals": signals}
    if impossible_travel and not matching_window:
        return {"verdict": "block", "confidence": 0.92, "signals": signals}

    # Foreign tx but customer declared the travel window → approve with the
    # explicit memory citation.
    if foreign_country and matching_window:
        return {"verdict": "approve", "confidence": 0.82, "signals": signals}

    # Domestic / non-flagged pending tx with no risk markers → approve.
    return {"verdict": "approve", "confidence": 0.88, "signals": signals}


__all__ = ["evaluate_verdict_fast"]
