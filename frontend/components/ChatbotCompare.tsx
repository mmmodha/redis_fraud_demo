"use client";
import { useState } from "react";
import { chatContextSurface, chatNaiveRag } from "@/lib/api";
import { mockChat } from "@/lib/mock";
import type { ChatResponse, HeroProfile, TraceStep } from "@/lib/types";
import { JsonTree } from "@/components/JsonTree";
import { Prose } from "@/components/Prose";
import { COMPONENT_CHIP, COMPONENT_LABEL } from "@/lib/traceColors";

const PROMPTS = [
  "Any upcoming travel?",
  "What's their typical spend?",
  "Are there any disputes?",
  "Is this card showing new devices?",
];

interface Turn {
  q: string;
  context: ChatResponse | null;
  naive: ChatResponse | null;
  loading: boolean;
}

export function ChatbotCompare({ hero }: { hero: HeroProfile | null }) {
  const [input, setInput] = useState("");
  const [turn, setTurn] = useState<Turn | null>(null);

  async function send(q: string) {
    if (!hero || !q.trim()) return;
    setTurn({ q, context: null, naive: null, loading: true });
    const req = { customer_id: hero.customer_id, message: q };
    const [ctx, naive] = await Promise.all([
      chatContextSurface(req).catch(() => mockChat(hero.customer_id, q, "context") as ChatResponse),
      chatNaiveRag(req).catch(() => mockChat(hero.customer_id, q, "naive") as ChatResponse),
    ]);
    setTurn({ q, context: ctx, naive, loading: false });
  }

  return (
    <section className="rounded-redis border border-redis-border bg-redis-bg-secondary">
      <div className="sticky top-[72px] z-20 flex items-center justify-between gap-3 rounded-t-redis border-b border-redis-border bg-redis-bg-secondary/95 px-5 py-3 backdrop-blur">
        <div>
          <div className="font-redis-body text-base font-semibold">Insight Chatbot — same model, different context</div>
          <div className="font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted">
            Same Claude model · Same policy docs · Different context
          </div>
        </div>
        <span className="font-redis-mono text-[11px] text-redis-text-muted">
          {hero ? hero.customer_id : "select a hero"}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 p-5 lg:grid-cols-2">
        <Pane
          title="Context Surface"
          subtitle="Customer-scoped tools + Agent Memory + Policy RAG"
          tone="hyper"
          testid="pane-context"
          loading={turn?.loading ?? false}
          turn={turn ? { q: turn.q, resp: turn.context } : null}
          emptyHint={hero ? `Ask a question about ${hero.firstName} \u2014 both pipelines will answer side-by-side.` : "Select a hero first."}
        />
        <Pane
          title="Naive RAG"
          subtitle="Policy-doc retrieval only \u2014 no customer context"
          tone="muted"
          testid="pane-naive"
          loading={turn?.loading ?? false}
          turn={turn ? { q: turn.q, resp: turn.naive } : null}
          emptyHint={hero ? `Ask a question about ${hero.firstName} \u2014 both pipelines will answer side-by-side.` : "Select a hero first."}
        />
      </div>

      <div className="border-t border-redis-border px-5 py-3">
        <div className="flex flex-wrap gap-2" data-testid="chat-prompts">
          {PROMPTS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => send(p)}
              className="rounded-redis border border-redis-border bg-redis-bg-tertiary px-3 py-1.5 font-redis-body text-xs text-redis-text-secondary transition-colors hover:border-redis-hyper hover:text-redis-text"
            >
              {p}
            </button>
          ))}
        </div>
        <form
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
  emptyHint,
}: {
  title: string;
  subtitle: string;
  tone: "hyper" | "muted";
  testid: string;
  loading: boolean;
  turn: { q: string; resp: ChatResponse | null } | null;
  emptyHint: string;
}) {
  return (
    <div
      data-testid={testid}
      className={`rounded-redis border bg-redis-bg-tertiary p-4 ${
        tone === "hyper" ? "border-l-[4px] border-l-redis-hyper border-redis-border" : "border-redis-border"
      }`}
    >
      <div className="font-redis-body text-sm font-semibold">{title}</div>
      <div className="mt-0.5 font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
        {subtitle}
      </div>
      <div className="mt-3 min-h-[150px] space-y-2">
        {!turn && (
          <div className="font-redis-body text-sm text-redis-text-muted">
            {emptyHint}
          </div>
        )}
        {turn && (
          <>
            <div className="min-w-0 max-w-full break-words rounded-redis bg-redis-bg-secondary px-3 py-2 font-redis-body text-xs text-redis-text-secondary">
              {turn.q}
            </div>
            <div data-testid={`${testid}-answer`} className="min-w-0 max-w-full break-words rounded-redis border border-redis-border bg-redis-bg-secondary px-3 py-2 font-redis-body text-sm text-redis-text">
              {loading ? (
                "Thinking…"
              ) : turn.resp?.answer ? (
                <Prose text={turn.resp.answer} className="space-y-2" />
              ) : (
                "(no answer)"
              )}
            </div>
            {turn.resp && !loading && (
              <TraceBreakdown resp={turn.resp} tone={tone} testid={testid} />
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
  // Redis call count excludes pure LLM steps — that is the comparison the
  // audience cares about (depth of Redis usage), not total step count.
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
  // Strip token counts from LLM output — not interesting to the audience.
  const cleanedOutput =
    isLlm && step.output_data
      ? Object.fromEntries(
          Object.entries(step.output_data).filter(
            ([k]) => k !== "input_tokens" && k !== "output_tokens",
          ),
        )
      : step.output_data;
  const inputEntries = Object.entries(step.input ?? {});
  const inputIsSmall = inputEntries.length > 0 && inputEntries.length <= 5;
  const outputEntries = cleanedOutput ? Object.entries(cleanedOutput) : [];
  const showOutputData = outputEntries.length > 0 && outputEntries.length < 8;

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={`flex w-full items-center justify-between gap-2 rounded-redis border px-2 py-1 text-left font-redis-mono text-[11px] transition-colors hover:brightness-110 ${chip} ${
          isLlm ? "opacity-70" : ""
        }`}
      >
        <span className="flex items-center gap-2 truncate">
          <span className="text-[9px] opacity-60">{open ? "▼" : "▶"}</span>
          <span className="font-bold uppercase tracking-wider">{label}</span>
          <span className="opacity-80">·</span>
          <span className="truncate">{step.tool}</span>
        </span>
        <span className="shrink-0 opacity-80">{step.latency_ms}ms</span>
      </button>
      {open && (
        <div className="mt-1 max-h-80 min-w-0 max-w-full space-y-1.5 overflow-hidden overflow-y-auto rounded-redis border border-redis-border bg-redis-bg-secondary px-3 py-2 font-redis-mono text-[11px]">
          <div className="font-redis-body text-[11px] font-semibold text-redis-text">
            {step.component}.{step.tool}
          </div>
          {inputEntries.length > 0 && (
            <div>
              <span className="text-redis-text-muted">Args: </span>
              {inputIsSmall ? (
                <span className="whitespace-pre-wrap break-all text-redis-text">
                  {inputEntries
                    .map(([k, v]) => `${k}=${typeof v === "string" ? `"${v}"` : String(v)}`)
                    .join(", ")}
                </span>
              ) : (
                <JsonTree data={step.input} defaultOpen />
              )}
            </div>
          )}
          <div>
            <span className="text-redis-text-muted">Output: </span>
            <span className="break-words text-redis-text">{step.output_summary}</span>
          </div>
          {showOutputData && (
            <div>
              <span className="text-redis-text-muted">Data: </span>
              <JsonTree data={cleanedOutput} defaultOpen />
            </div>
          )}
          {step.redis_keys_touched.length > 0 && (
            <div>
              <span className="text-redis-text-muted">Redis keys: </span>
              <span className="break-all text-redis-text">
                {step.redis_keys_touched.join(", ")}
              </span>
            </div>
          )}
          <div>
            <span className="text-redis-text-muted">Latency: </span>
            <span className="text-redis-text">{step.latency_ms} ms</span>
          </div>
        </div>
      )}
    </li>
  );
}
