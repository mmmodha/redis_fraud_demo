// Catch-all proxy: forwards browser /api/* calls to the backend container.
// Replaces next.config.mjs `rewrites()` because rewrites reuse Node's
// HTTP keep-alive pool — after `docker compose restart backend` the pooled
// sockets point at the dead container IP and every request fails with
// ECONNREFUSED / socket hang up until the frontend is also restarted.
// This handler disables connection reuse and retries once on transient
// connect errors so backend rebuilds are invisible to the UI.

import type { NextRequest } from "next/server";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";

const TRANSIENT_CODES = new Set([
  "ECONNRESET",
  "ECONNREFUSED",
  "UND_ERR_SOCKET",
  "UND_ERR_CONNECT_TIMEOUT",
  "ETIMEDOUT",
  "EAI_AGAIN",
]);

function classifyError(err: unknown): { transient: boolean; code: string } {
  const e = err as { code?: string; cause?: { code?: string }; message?: string };
  const code = e?.code ?? e?.cause?.code ?? "";
  const msg = (e?.message ?? "").toLowerCase();
  if (TRANSIENT_CODES.has(code)) return { transient: true, code };
  if (msg.includes("socket hang up") || msg.includes("fetch failed")) {
    return { transient: true, code: code || "FETCH_FAILED" };
  }
  return { transient: false, code: code || "UNKNOWN" };
}

async function forward(req: NextRequest, segments: string): Promise<Response> {
  const search = req.nextUrl.search ?? "";
  const url = `${BACKEND}/${segments}${search}`;
  const method = req.method.toUpperCase();

  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["content-type"] = ct;
  const accept = req.headers.get("accept");
  if (accept) headers["accept"] = accept;

  let body: ArrayBuffer | undefined;
  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    const buf = await req.arrayBuffer();
    if (buf.byteLength > 0) body = buf;
  }

  // `keepalive: false` + `cache: "no-store"` instructs fetch to avoid
  // connection reuse. `signal: req.signal` propagates client cancels.
  const init: RequestInit = {
    method,
    headers,
    body,
    cache: "no-store",
    keepalive: false,
    signal: req.signal,
  };

  return fetch(url, init);
}

async function proxy(req: NextRequest, path: string[] | undefined): Promise<Response> {
  const segments = (path ?? []).join("/");
  let upstream: Response;
  try {
    upstream = await forward(req, segments);
  } catch (err) {
    const { transient, code } = classifyError(err);
    if (!transient) {
      console.warn(`[fcc-proxy] non-transient code=${code} path=/${segments}`);
      return errorResponse(code, 502);
    }
    console.warn(`[fcc-proxy] transient code=${code} path=/${segments} — retrying once`);
    await new Promise((r) => setTimeout(r, 200));
    try {
      upstream = await forward(req, segments);
    } catch (err2) {
      const { code: code2 } = classifyError(err2);
      console.warn(`[fcc-proxy] retry failed code=${code2} path=/${segments}`);
      return errorResponse(code2, 502);
    }
  }

  const respHeaders = new Headers(upstream.headers);
  respHeaders.set("x-fcc-proxy", "route-handler");
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  });
}

function errorResponse(code: string, status: number): Response {
  return new Response(JSON.stringify({ error: "upstream_unreachable", code }), {
    status,
    headers: {
      "content-type": "application/json",
      "x-fcc-proxy": "route-handler",
    },
  });
}

type Ctx = { params: Promise<{ path?: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function OPTIONS(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}

export const dynamic = "force-dynamic";
