// API client for the FastAPI backend. Browser code hits same-origin `/api/*`
// which Next.js rewrites to the backend container (see next.config.mjs) so we
// avoid CORS. NEXT_PUBLIC_BACKEND_URL still works as an override for `next dev`
// against a directly-reachable backend.

import type {
  ChatRequest,
  ChatResponse,
  HeroProfile,
  OtpConfirmResponse,
  RdiStatus,
  ScoreResponse,
  TraceStep,
  VerdictFastResponse,
} from "./types";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "/api";

async function postJSON<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST ${path} ${res.status}: ${text}`);
  }
  return (await res.json()) as T;
}

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} ${res.status}`);
  return (await res.json()) as T;
}

export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const h = await getJSON<{ redis: string; postgres: string }>("/health", signal);
    return h.redis === "ok" && h.postgres === "ok";
  } catch {
    return false;
  }
}

// Wave 7n: optional `bypassCache` sends `X-Bypass-Cache: 1` so the backend
// skips the cache GET and runs the agent fresh. The backend still writes
// the new result through to cache so the next normal click is cached again.
export interface ScoreOpts {
  bypassCache?: boolean;
}

export async function scoreHero(
  hero: HeroProfile,
  signal?: AbortSignal,
  opts: ScoreOpts = {},
): Promise<ScoreResponse> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (opts.bypassCache) headers["x-bypass-cache"] = "1";
  const res = await fetch(`${BACKEND_URL}/agent/score`, {
    method: "POST",
    headers,
    body: JSON.stringify({ customer_id: hero.customer_id, transaction: hero.transaction }),
    signal,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST /agent/score ${res.status}: ${text}`);
  }
  return (await res.json()) as ScoreResponse;
}

// Streaming variant of `scoreHero` (Wave 7j). Hits `/agent/score/stream` and
// parses NDJSON line-by-line so the trace strip + right-rail panels populate
// as each backend tool call lands, instead of waiting ~30s for the final
// payload. Handlers map 1:1 onto the backend event contract.
export interface ScoreStreamHandlers {
  onThinking?: (round: number) => void;
  onStep?: (step: TraceStep) => void;
  onFinal?: (response: ScoreResponse) => void;
}

export async function scoreHeroStream(
  hero: HeroProfile,
  handlers: ScoreStreamHandlers,
  signal?: AbortSignal,
  opts: ScoreOpts = {},
): Promise<void> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (opts.bypassCache) headers["x-bypass-cache"] = "1";
  const res = await fetch(`${BACKEND_URL}/agent/score/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      customer_id: hero.customer_id,
      transaction: hero.transaction,
    }),
    signal,
    cache: "no-store",
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST /agent/score/stream ${res.status}: ${text}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  const dispatch = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    let event: { type?: string; round?: number; step?: TraceStep; response?: ScoreResponse };
    try {
      event = JSON.parse(trimmed);
    } catch {
      return;
    }
    if (event.type === "thinking" && typeof event.round === "number") {
      handlers.onThinking?.(event.round);
    } else if (event.type === "step" && event.step) {
      handlers.onStep?.(event.step);
    } else if (event.type === "final" && event.response) {
      handlers.onFinal?.(event.response);
    }
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      dispatch(buf.slice(0, nl));
      buf = buf.slice(nl + 1);
    }
  }
  if (buf.length > 0) dispatch(buf);
}

export async function fetchVerdictFast(
  hero: HeroProfile,
  signal?: AbortSignal,
): Promise<VerdictFastResponse> {
  return postJSON<VerdictFastResponse>(
    "/agent/verdict-fast",
    { customer_id: hero.customer_id, transaction: hero.transaction },
    signal,
  );
}

export async function confirmOtp(
  transactionId: string,
  signal?: AbortSignal,
): Promise<OtpConfirmResponse> {
  return postJSON<OtpConfirmResponse>(
    "/agent/otp-confirm",
    { transaction_id: transactionId },
    signal,
  );
}

export async function chatContextSurface(req: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  return postJSON<ChatResponse>("/chat/context-surface", req, signal);
}

export async function chatNaiveRag(req: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  return postJSON<ChatResponse>("/chat/naive-rag", req, signal);
}

export async function getRdiStatus(signal?: AbortSignal): Promise<RdiStatus | null> {
  try {
    return await getJSON<RdiStatus>("/rdi/status", signal);
  } catch {
    return null;
  }
}

// Wave 7n: presenter affordance to wipe the Redis verdict cache so a fresh
// run goes through the full agent path again. Body is optional — passing a
// `customer_id` scopes the clear to that hero.
export async function clearDemoCache(
  customerId?: string,
  signal?: AbortSignal,
): Promise<{ cleared: number }> {
  return postJSON<{ cleared: number }>(
    "/agent/cache/clear",
    customerId ? { customer_id: customerId } : {},
    signal,
  );
}

export async function getFeatures(cardId: string, signal?: AbortSignal): Promise<Record<string, unknown> | null> {
  try {
    const r = await getJSON<{ card_id: string; features: Record<string, unknown> }>(
      `/debug/features/${encodeURIComponent(cardId)}`,
      signal,
    );
    return r.features;
  } catch {
    return null;
  }
}
