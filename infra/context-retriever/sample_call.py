"""Tiny e2e probe: call one MCP tool with CTX_AGENT_KEY and print a summary.

Used by ``scripts/context-up.sh`` as the final smoke-test step. Inputs come
from the command line so the script itself never logs CTX_AGENT_KEY.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from context_surfaces import UnifiedClient


CANDIDATE_TOOLS = (
    "get_customer_by_customer_id",
    "get_customer",
    "Customer_by_customer_id",
    "get_customer_by_id",
)


async def main(customer_id: str) -> int:
    agent_key = os.environ.get("CTX_AGENT_KEY", "").strip()
    if not agent_key:
        print("ERROR: CTX_AGENT_KEY missing", file=sys.stderr)
        return 2
    async with UnifiedClient() as client:
        tools = await client.list_tools(agent_key)
        names = [t.get("name") for t in tools if isinstance(t, dict)]
        # Prefer an exact match from our candidate list; otherwise fall back
        # to any tool name that looks like a customer-by-id getter.
        chosen = next((n for n in CANDIDATE_TOOLS if n in names), None)
        if not chosen:
            chosen = next(
                (n for n in names if n and "customer" in n.lower() and ("id" in n.lower() or "get" in n.lower())),
                None,
            )
        if not chosen:
            print(f"no customer-by-id tool found in: {names}", file=sys.stderr)
            return 3
        # Try a couple of arg names since the auto-generated schema may use
        # either "customer_id" or "id".
        last_err: Exception | None = None
        for arg_name in ("customer_id", "id", "key"):
            try:
                result = await client.query_tool(agent_key, chosen, {arg_name: customer_id})
                summary = result if isinstance(result, dict) else {"result": result}
                print(f"TOOL={chosen} ARG={arg_name}")
                print(json.dumps(summary, indent=2, default=str)[:600])
                return 0
            except Exception as exc:  # noqa: BLE001 — best-effort smoke probe
                last_err = exc
        print(f"call to {chosen} failed for all arg shapes: {last_err}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    cust = sys.argv[1] if len(sys.argv) > 1 else "cust_mike"
    sys.exit(asyncio.run(main(cust)))
