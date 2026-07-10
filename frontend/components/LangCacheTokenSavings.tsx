"use client";

import type { ChatResponse } from "@/lib/types";

export function totalTokens(resp: ChatResponse | null): number {
  if (!resp) return 0;
  if (resp.cached) return 0;
  return (resp.input_tokens ?? 0) + (resp.output_tokens ?? 0);
}

export function tokensSaved(resp: ChatResponse | null): number {
  if (!resp?.cached) return 0;
  return (resp.tokens_saved_input ?? 0) + (resp.tokens_saved_output ?? 0);
}

interface SessionCounterProps {
  sessionSaved: number;
}

export function LangCacheSessionCounter({ sessionSaved }: SessionCounterProps) {
  return (
    <div
      data-testid="langcache-session-counter"
      className="flex items-center gap-2 rounded-redis border border-redis-border bg-redis-bg-tertiary px-3 py-1.5"
    >
      <span className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-hyper">
        LangCache
      </span>
      {sessionSaved > 0 ? (
        <span className="langcache-counter-pop font-redis-mono text-xs font-bold text-verdict-approve">
          {sessionSaved.toLocaleString()} tokens saved this session
        </span>
      ) : (
        <span className="font-redis-mono text-[11px] text-redis-text-muted">
          0 saved — ask the same question again
        </span>
      )}
    </div>
  );
}

interface HitBannerProps {
  resp: ChatResponse;
}

export function LangCacheHitBanner({ resp }: HitBannerProps) {
  const saved = tokensSaved(resp);
  const matchLabel =
    resp.cache_match_type === "semantic"
      ? `Semantic match${resp.cache_similarity ? ` (${Math.round(resp.cache_similarity * 100)}% similar)` : ""}`
      : "Exact match";

  return (
    <div
      data-testid="langcache-hit-banner"
      className="langcache-hit-banner mb-2 rounded-redis border border-l-[4px] border-l-verdict-approve border-verdict-approve/30 bg-verdict-approve/10 px-3 py-2 font-redis-body text-xs text-verdict-approve"
    >
      LangCache HIT — {resp.tokens_saved_input ?? 0} in + {resp.tokens_saved_output ?? 0} out
      tokens saved ({saved.toLocaleString()} total) · {resp.cache_latency_ms ?? 0}ms · {matchLabel}
    </div>
  );
}

interface SavingsBarProps {
  resp: ChatResponse;
}

export function LangCacheSavingsBar({ resp }: SavingsBarProps) {
  const saved = tokensSaved(resp);
  const llmTotal = saved || totalTokens(resp) || 1000;
  const pct = Math.max(4, Math.min(100, (saved / llmTotal) * 100));

  return (
    <div data-testid="langcache-savings-bar" className="mt-2 space-y-1.5">
      <div className="flex justify-between font-redis-mono text-[10px] uppercase tracking-wider">
        <span className="text-redis-text-muted line-through">
          {llmTotal.toLocaleString()} tokens (LLM path)
        </span>
        <span className="font-bold text-verdict-approve">
          {saved.toLocaleString()} tokens saved
        </span>
      </div>
      <div className="relative h-3 overflow-hidden rounded-full bg-redis-bg-secondary">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-redis-text-muted/25"
          style={{ width: "100%" }}
        />
        <div
          className="langcache-bar-fill absolute inset-y-0 left-0 rounded-full bg-verdict-approve"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

interface BaselineRowProps {
  resp: ChatResponse;
}

export function LangCacheBaselineRow({ resp }: BaselineRowProps) {
  const inT = resp.input_tokens ?? 0;
  const outT = resp.output_tokens ?? 0;
  return (
    <div
      data-testid="langcache-baseline"
      className="mt-2 font-redis-mono text-[11px] text-redis-text-muted"
    >
      LLM call · {inT} in · {outT} out · {(inT + outT).toLocaleString()} total tokens ·{" "}
      {resp.trace.total_latency_ms}ms
    </div>
  );
}

interface TurnComparisonProps {
  prior: ChatResponse;
  current: ChatResponse;
}

export function LangCacheTurnComparison({ prior, current }: TurnComparisonProps) {
  const priorIn = prior.input_tokens ?? 820;
  const priorOut = prior.output_tokens ?? 180;
  return (
    <div
      data-testid="langcache-turn-comparison"
      className="mt-2 overflow-hidden rounded-redis border border-redis-border text-[11px]"
    >
      <table className="w-full font-redis-mono">
        <thead>
          <tr className="border-b border-redis-border bg-redis-bg-secondary text-redis-text-muted">
            <th className="px-2 py-1 text-left font-normal"> </th>
            <th className="px-2 py-1 text-left font-normal">Tokens</th>
            <th className="px-2 py-1 text-left font-normal">Latency</th>
          </tr>
        </thead>
        <tbody>
          <tr className="text-redis-text-muted">
            <td className="px-2 py-1">First ask (LLM)</td>
            <td className="px-2 py-1">
              {priorIn} in · {priorOut} out
            </td>
            <td className="px-2 py-1">{prior.trace.total_latency_ms}ms</td>
          </tr>
          <tr className="bg-verdict-approve/10 text-verdict-approve">
            <td className="px-2 py-1 font-semibold">Second ask (LangCache)</td>
            <td className="px-2 py-1 font-bold">0</td>
            <td className="px-2 py-1 font-bold">{current.cache_latency_ms ?? 0}ms</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

interface VerdictSavingsProps {
  cacheLatencyMs?: number | null;
  tokensSavedEstimate?: number;
}

export function LangCacheVerdictSavings({
  cacheLatencyMs,
  tokensSavedEstimate = 2480,
}: VerdictSavingsProps) {
  return (
    <div
      data-testid="langcache-verdict-savings"
      data-guide="langcache-verdict"
      className="mt-2 rounded-redis border border-l-[4px] border-l-verdict-approve border-verdict-approve/30 bg-verdict-approve/10 px-3 py-2 font-redis-mono text-[11px] text-verdict-approve"
    >
      LangCache replay · ~{tokensSavedEstimate.toLocaleString()} tokens skipped · agent trace
      served in {cacheLatencyMs ?? 6}ms
    </div>
  );
}
