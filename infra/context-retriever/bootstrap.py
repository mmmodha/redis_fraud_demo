"""Idempotent Context Retriever surface + agent provisioner.

Runs inside the ``context-retriever-bootstrap`` Docker image (Python 3.12 +
``redis-context-retriever``). Reads admin key + Redis connection from env,
finds-or-creates the ``fraud-command-center`` surface, mints a fresh agent
key, and writes ``CTX_SURFACE_ID`` + ``CTX_AGENT_KEY`` back to the mounted
``.env``. Secrets are never echoed (only ``SURFACE_ID`` is printed, agent key
goes straight to ``.env``).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from context_surfaces import (
    ContextSurfacesClient,
    CreateAgentKeyRequest,
    CreateContextSurfaceRequest,
    DataSourceConnectionConfig,
    DataSourceRequest,
    UnifiedClient,
    export_data_model,
)

sys.path.insert(0, "/work/backend")
from app import context_models  # noqa: E402

SURFACE_NAME = os.environ.get("CTX_SURFACE_NAME", "").strip() or "fraud-command-center"
AGENT_NAME = "fraud-agent"
ENV_FILE = Path(os.environ.get("CTX_ENV_FILE", "/work/.env"))


def _parse_redis_url(url: str) -> tuple[str, int, str, str, bool]:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "redis").lower()
    if scheme not in ("redis", "rediss"):
        raise SystemExit(f"unsupported scheme {scheme}://")
    host = parsed.hostname or ""
    port = parsed.port or (6380 if scheme == "rediss" else 6379)
    username = parsed.username or "default"
    password = parsed.password or ""
    if not host or not password:
        raise SystemExit("REDIS_URL must include host and password")
    return host, port, username, password, scheme == "rediss"


def _upsert_env(updates: dict[str, str]) -> None:
    ENV_FILE.touch(exist_ok=True)
    lines = ENV_FILE.read_text().splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    for key, val in updates.items():
        if key not in seen:
            out.append(f"{key}={val}")
    ENV_FILE.write_text("\n".join(out).rstrip() + "\n")


async def _find_surface(client: ContextSurfacesClient, admin_key: str):
    page = 1
    while True:
        resp = await client.list_context_surfaces(admin_key=admin_key, page=page, page_size=50)
        for surface in resp.context_surfaces:
            if surface.name == SURFACE_NAME:
                return surface
        pag = getattr(resp, "pagination", None)
        if not pag or not getattr(pag, "has_more", False):
            return None
        page += 1


async def main() -> int:
    admin_key = os.environ.get("CTX_ADMIN_KEY", "").strip()
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not admin_key:
        print("ERROR: CTX_ADMIN_KEY missing in container env", file=sys.stderr)
        return 2
    if not redis_url:
        print("ERROR: REDIS_URL missing in container env", file=sys.stderr)
        return 2
    host, port, username, password, tls = _parse_redis_url(redis_url)

    data_model = export_data_model(
        title="Fraud Command Center",
        description="Bank fraud-detection demo: customers, accounts, cards, devices, merchants, transactions.",
        entities=list(context_models.CONTEXT_MODELS),
    )

    async with ContextSurfacesClient() as client:
        existing = await _find_surface(client, admin_key)
        if existing is not None:
            surface_id = existing.id
            print(f"SURFACE_ID={surface_id}  (reused existing '{SURFACE_NAME}')")
        else:
            req = CreateContextSurfaceRequest(
                name=SURFACE_NAME,
                description="Fraud Command Center demo surface (auto-provisioned).",
                data_model=data_model,
                data_source=DataSourceRequest(
                    connection_config=DataSourceConnectionConfig(
                        addr=f"{host}:{port}",
                        username=username,
                        password=password,
                        db=0,
                        tls_enabled=tls,
                    ),
                ),
            )
            created = await client.create_context_surface(req, admin_key=admin_key)
            surface_id = created.id
            print(f"SURFACE_ID={surface_id}  (created '{SURFACE_NAME}')")

        agent = await client.create_agent_key(
            surface_id,
            CreateAgentKeyRequest(
                name=f"{AGENT_NAME}-{os.getpid()}",
                description="Fraud Command Center demo agent (auto-provisioned).",
            ),
            admin_key=admin_key,
        )
        if not agent.key:
            print("ERROR: agent key value missing from API response", file=sys.stderr)
            return 3
        print("AGENT_KEY=<redacted, written to .env>")
        cr_console_url = f"https://app.redislabs.com/#/context-retriever/{surface_id}"
        _upsert_env({
            "CTX_SURFACE_ID": surface_id,
            "CTX_AGENT_KEY": agent.key,
            "NEXT_PUBLIC_CONTEXT_RETRIEVER_URL": cr_console_url,
        })
        print(f"wrote CTX_SURFACE_ID + CTX_AGENT_KEY + NEXT_PUBLIC_CONTEXT_RETRIEVER_URL -> {ENV_FILE}")
        print(f"CONTEXT_RETRIEVER_URL={cr_console_url}")

        async with UnifiedClient() as u:
            tools = await u.list_tools(agent.key)
            print(f"TOOLS_COUNT={len(tools)}")
            tool_names = sorted({t.get("name") for t in tools if isinstance(t, dict) and t.get("name")})
            print("TOOLS=" + json.dumps(tool_names))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
