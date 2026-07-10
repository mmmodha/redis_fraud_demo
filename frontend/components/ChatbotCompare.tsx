"use client";
import { useEffect, useRef, useState } from "react";
import { chatContextSurface, chatNaiveRag } from "@/lib/api";
import { mockChat } from "@/lib/mock";
import type { ChatResponse, HeroProfile, TraceStep } from "@/lib/types";
import { JsonTree } from "@/components/JsonTree";
import { Prose } from "@/components/Prose";
import { COMPONENT_CHIP, COMPONENT_LABEL } from "@/lib/traceColors";
import { useDemoGuideOptional } from "@/components/DemoGuideProvider";
import { stepExpectsEvent } from "@/lib/demoGuide";
import {
  LangCacheBaselineRow,
  LangCacheHitBanner,
  LangCacheSavingsBar,
  LangCacheSessionCounter,
  LangCacheTurnComparison,
  tokensSaved,
} from "@/components/LangCacheTokenSavings";

const PROMPTS = [
  "Any upcoming travel?",
  "What's their typical spend?",
  "Are there any disputes?",
  "Is this card showing new devices?",
];

function normalizePrompt(q: string): string {
  return q.toLowerCase().trim().replace(/\s+/g, " ").replace(/[?.!]+$/, "");
}

interface Turn {
  q: string;
  context: ChatResponse | null;
  naive: ChatResponse | null;
  loading: boolean;
}

export function ChatbotCompare({ hero }: { hero: HeroProfile | null }) {
  const [input, setInput] = useState("");
  const [turn, setTurn] = useState<Turn | null>(null);
  const [sessionSaved, setSessionSaved] = useState(0);
  const [lastMissByPrompt, setLastMissByPrompt] = useState<
    Record<string, { context?: ChatResponse; naive?: ChatResponse }>
  >({});
  const sectionRef = useRef<HTMLElement>(null);
  const guide = useDemoGuideOptional();

  useEffect(() => {
    const el = sectionRef.current;
    if (!el || !guide?.guideMode) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting && stepExpectsEvent(guide?.currentStep ?? null, "scroll-chatbot")) {
          guide.completeAction({ type: "scroll-chatbot" });
        }
      },
      { threshold: 0.3 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [guide]);

  async function send(q: string, promptIndex?: number) {
    if (!hero || !q.trim()) return;
    setTurn({ q, context: null, naive: null, loading: true });
    const req = { customer_id: hero.customer_id, message: q };
    const [ctx, naive] = await Promise.all([
      chatContextSurface(req).catch(() => mockChat(hero.customer_id, q, "context") as ChatResponse),
      chatNaiveRag(req).catch(() => mockChat(hero.customer_id, q, "naive") as ChatResponse),
    ]);
    setTurn({ q, context: ctx, naive, loading: false });

    const key = normalizePrompt(q);
    const ctxSaved = tokensSaved(ctx);
    const naiveSaved = tokensSaved(naive);
    if (ctxSaved + naiveSaved > 0) {
      setSessionSaved((s) => s + ctxSaved + naiveSaved);
      if (stepExpectsEvent(guide?.currentStep ?? null, "chat-cache-hit")) {
        guide?.completeAction({ type: "chat-cache-hit" });
      }
    } else {
      setLastMissByPrompt((prev) => ({
        ...prev,
        [key]: { context: ctx, naive },
      }));
    }

    if (promptIndex !== undefined) {
      guide?.completeAction({ type: "chat-prompt", index: promptIndex });
    } else if (stepExpectsEvent(guide?.currentStep ?? null, "chat-sent")) {
      guide?.completeAction({ type: "chat-sent" });
    }
  }

  return (
    <section
      ref={sectionRef}
      data-guide="chatbot"
      className="rounded-redis border border-redis-border bg-redis-bg-secondary"
    >
      <div className="sticky top-[72px] z-20 flex flex-wrap items-center justify-between gap-3 rounded-t-redis border-b border-redis-border bg-redis-bg-secondary/95 px-5 py-3 backdrop-blur">
        <div>
          <div className="font-redis-body text-base font-semibold">
            Insight Chatbot — same model, different context
          </div>
          <div className="font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted">
            Same LLM · Same policy docs · Different context
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div data-guide="langcache-savings">
            <LangCacheSessionCounter sessionSaved={sessionSaved} />
          </div>
          <span className="font-redis-mono text-[11px] text-redis-text-muted">
            {hero ? hero.customer_id : "select a hero"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 p-5 lg:grid-cols-2">
        <Pane
          title="Context Surface"
          subtitle="Customer-scoped tools + Agent Memory + Policy RAG"
          tone="hyper"
          testid="pane-context"
          loading={turn?.loading ?? false}
          turn={turn ? { q: turn.q, resp: turn.context } : null}
          priorMiss={turn ? lastMissByPrompt[normalizePrompt(turn.q)]?.context : undefined}
          emptyHint={
            hero
              ? `Ask a question about ${hero.firstName} — both pipelines will answer side-by-side.`
              : "Select a hero first."
          }
        />
        <Pane
          title="Naive RAG"
          subtitle="Policy-doc retrieval only — no customer context"
          tone="muted"
          testid="pane-naive"
          loading={turn?.loading ?? false}
          turn={turn ? { q: turn.q, resp: turn.naive } : null}
          priorMiss={turn ? lastMissByPrompt[normalizePrompt(turn.q)]?.naive : undefined}
          emptyHint={
            hero
              ? `Ask a question about ${hero.firstName} — both pipelines will answer side-by-side.`
              : "Select a hero first."
          }
        />
      </div>

      <div className="border-t border-redis-border px-5 py-3">
        <div className="flex flex-wrap gap-2" data-testid="chat-prompts">
          {PROMPTS.map((p, i) => (
            <button
              key={p}
              type="button"
              data-guide={`chat-prompt-${i}`}
              onClick={() => send(p, i)}
              className="rounded-redis border border-redis-border bg-redis-bg-tertiary px-3 py-1.5 font-redis-body text-xs text-redis-text-secondary transition-colors hover:border-redis-hyper hover:text-redis-text"
            >
              {p}
            </button>
          ))}
        </div>
        <form
          data-guide="chat-send"
          data-testid="chat-send-form"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
            setInput("");
          }}
          className="mt-3 flex gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={hero ? `Ask about ${hero.name}…` : "Select a hero first"}
            disabled={!hero}
            data-testid="chat-input"
            className="min-h-11 flex-1 rounded-redis border border-redis-border-secondary bg-redis-bg-tertiary px-4 py-2 font-redis-body text-sm text-redis-text placeholder:text-redis-text-muted focus:border-redis-hyper focus:outline-none"
          />
          <button
            type="submit"
            disabled={!hero || !input.trim()}
            data-testid="chat-ask-both"
            data-guide="chat-ask-both"
            className="min-h-11 rounded-redis border border-redis-border border-l-[4px] border-l-redis-hyper bg-redis-bg-tertiary px-5 font-redis-body text-sm font-semibold text-redis-text hover:bg-redis-border disabled:opacity-50"
          >
            Ask both
          </button>
        </form>
      </div>
    </section>
  );
}

function Pane({
  title,
  subtitle,
  tone,
  testid,
  loading,
  turn,
  priorMiss,
  emptyHint,
}: {
  title: string;
  subtitle: string;
  tone: "hyper" | "muted";
  testid: string;
  loading: boolean;
  turn: { q: string; resp: ChatResponse | null } | null;
  priorMiss?: ChatResponse;
  emptyHint: string;
}) {
  const resp = turn?.resp;
  const showHit = resp?.cached === true;
  const showComparison = showHit && priorMiss;

  return (
    <div
      data-testid={testid}
      className={`rounded-redis border bg-redis-bg-tertiary p-4 ${
        tone === "hyper"
          ? "border-l-[4px] border-l-redis-hyper border-redis-border"
          : "border-redis-border"
      }`}
    >
      <div className="font-redis-body text-sm font-semibold">{title}</div>
      <div className="mt-0.5 font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
        {subtitle}
      </div>
      <div className="mt-3 min-h-[150px] space-y-2">
        {!turn && (
          <div className="font-redis-body text-sm text-redis-text-muted">{emptyHint}</div>
        )}
        {turn && (
          <>
            <div className="min-w-0 max-w-full break-words rounded-redis bg-redis-bg-secondary px-3 py-2 font-redis-body text-xs text-redis-text-secondary">
              {turn.q}
            </div>
            {showHit && resp && <LangCacheHitBanner resp={resp} />}
            <div
              data-testid={`${testid}-answer`}
              className="min-w-0 max-w-full break-words rounded-redis border border-redis-border bg-redis-bg-secondary px-3 py-2 font-redis-body text-sm text-redis-text"
            >
              {loading ? (
                "Thinking…"
              ) : resp?.answer ? (
                <Prose text={resp.answer} className="space-y-2" />
              ) : (
                "(no answer)"
              )}
            </div>
            {resp && !loading && showHit && <LangCacheSavingsBar resp={resp} />}
            {resp && !loading && !showHit && <LangCacheBaselineRow resp={resp} />}
            {resp && !loading && showComparison && priorMiss && (
              <LangCacheTurnComparison prior={priorMiss} current={resp} />
            )}
            {resp && !loading && (
              <TraceBreakdown resp={resp} tone={tone} testid={testid} />
            )}
          </>
        )}
      </div>
    </div>
  );
}

function TraceBreakdown({
  resp,
  tone,
  testid,
}: {
  resp: ChatResponse;
  tone: "hyper" | "muted";
  testid: string;
}) {
  const steps = resp.trace.steps;
  const redisCalls = steps.filter((s) => s.component !== "llm").length;
  const totalMs = resp.trace.total_latency_ms;
  const callLabel = redisCalls === 1 ? "Redis call" : "Redis calls";

  return (
    <div data-testid={`${testid}-trace`} className="mt-1">
      <div className="flex items-baseline justify-between gap-2">
        <div className="font-redis-mono text-[13px] font-bold text-redis-text">
          <span data-testid={`${testid}-trace-count`}>{redisCalls}</span> {callLabel}
          <span className="mx-1.5 text-redis-text-muted">·</span>
          <span data-testid={`${testid}-trace-latency`}>{totalMs}ms</span>
        </div>
        <span className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
          {steps.length} step{steps.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="mt-1 font-redis-body text-[11px] text-redis-text-muted">
        {tone === "hyper"
          ? "Redis is in-memory — every call is single-to-double-digit ms. The depth is essentially free."
          : "Same model, same policy docs — but no customer context."}
      </div>
      <ul className="mt-2 space-y-1.5">
        {steps.map((step, i) => (
          <TraceRow key={i} step={step} />
        ))}
      </ul>
    </div>
  );
}

function TraceRow({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  const chip = COMPONENT_CHIP[step.component];
  const label = COMPONENT_LABEL[step.component];
  const isLlm = step.component === "llm";
  const cleanedOutput = step.output_data;
  const inputEntries = Object.entries(step.input ?? {});
  const inputIsSmall = inputEntries.length > 0 && inputEntries.length <= 5;
  const outputEntries = cleanedOutput ? Object.entries(cleanedOutput) : [];
  const showOutputData = outputEntries.length > 0 && outputEntries.length < 8;

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-redis border border-redis-border bg-redis-bg-secondary px-2 py-1.5 text-left font-redis-mono text-[11px] hover:bg-redis-bg-tertiary"
      >
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${chip}`}
        >
          {label}
        </span>
        <span className="flex-1 truncate text-redis-text-secondary">{step.tool}</span>
        <span className="text-redis-text-muted">{step.latency_ms}ms</span>
        <span className="text-redis-text-muted">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="max-h-80 overflow-y-auto rounded-redis border border-redis-border bg-redis-bg-secondary p-2 mt-1">
          <div className="font-redis-mono text-[10px] text-redis-text-muted">
            {step.output_summary}
          </div>
          {inputIsSmall && (
            <div className="mt-2">
              <div className="font-redis-mono text-[10px] uppercase text-redis-text-muted">Input</div>
              <JsonTree data={step.input} />
            </div>
          )}
          {showOutputData && (
            <div className="mt-2">
              <div className="font-redis-mono text-[10px] uppercase text-redis-text-muted">
                Output
              </div>
              <JsonTree data={cleanedOutput} />
            </div>
          )}
          {step.redis_keys_touched.length > 0 && (
            <div className="mt-2 font-redis-mono text-[10px] text-redis-text-link">
              {step.redis_keys_touched.join(" · ")}
            </div>
          )}
        </div>
      )}
    </li>
  );
}
