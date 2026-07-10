"use client";
import type {
  HeroProfile,
  OtpConfirmResponse,
  ScoreResponse,
  VerdictFastResponse,
} from "@/lib/types";
import { Prose } from "@/components/Prose";
import { LangCacheVerdictSavings } from "@/components/LangCacheTokenSavings";

const TONE = {
  approve: { label: "APPROVE", bg: "bg-verdict-approve", text: "text-verdict-approve", border: "border-verdict-approve/40", glow: "shadow-[0_0_40px_-12px_rgba(31,179,107,0.6)]" },
  review: { label: "REVIEWED", bg: "bg-verdict-review", text: "text-verdict-review", border: "border-verdict-review/40", glow: "shadow-[0_0_40px_-12px_rgba(226,160,63,0.6)]" },
  block: { label: "BLOCK", bg: "bg-verdict-block", text: "text-verdict-block", border: "border-verdict-block/40", glow: "shadow-[0_0_40px_-12px_rgba(255,68,56,0.65)]" },
} as const;

export type OtpState = "idle" | "sending" | "confirmed";

interface Props {
  // Wave 7i: Card A renders the verdict (or step-up breadcrumb for REVIEW
  // heroes), Card B renders the LLM Analyst Summary with a shimmer skeleton
  // while ``score`` is still in flight.
  fast: VerdictFastResponse | null;
  score: ScoreResponse | null;
  hero: HeroProfile | null;
  otpState: OtpState;
  otpResult: OtpConfirmResponse | null;
  otpLatencyMs: number;
}

export function VerdictCard({
  fast, score, hero, otpState, otpResult, otpLatencyMs,
}: Props) {
  if (!fast && !score) {
    return (
      <div className="rounded-redis border border-dashed border-redis-border bg-redis-bg-secondary p-8 text-center">
        <div className="font-redis-mono text-xs uppercase tracking-wider text-redis-text-muted">
          Verdict
        </div>
        <div className="mt-2 font-redis-body text-lg text-redis-text-secondary">
          Pick a hero and hit “Run scenario” to score a transaction.
        </div>
      </div>
    );
  }

  // Prefer the fast verdict for the badge so it appears instantly; once the
  // LLM resolves both verdicts should agree.
  const verdict = fast?.verdict ?? score!.verdict;
  const tone = TONE[verdict];
  const confidencePct = Math.round((score?.confidence ?? fast!.confidence) * 100);
  const latencyMs = fast?.total_latency_ms ?? score?.trace.total_latency_ms ?? 0;

  const cached = score?.cached === true;

  return (
    <div className="space-y-4">
      <div data-guide="verdict-card">
        <VerdictBlock
          verdict={verdict}
          tone={tone}
          confidencePct={confidencePct}
          latencyMs={latencyMs}
          fast={fast}
          hero={hero}
          otpState={otpState}
          otpResult={otpResult}
          otpLatencyMs={otpLatencyMs}
          cached={cached}
          cacheLatencyMs={score?.cache_latency_ms}
        />
      </div>
      <AnalystSummaryBlock score={score} />
    </div>
  );
}

interface BlockProps {
  verdict: keyof typeof TONE;
  tone: (typeof TONE)[keyof typeof TONE];
  confidencePct: number;
  latencyMs: number;
  fast: VerdictFastResponse | null;
  hero: HeroProfile | null;
  otpState: OtpState;
  otpResult: OtpConfirmResponse | null;
  otpLatencyMs: number;
  cached: boolean;
  cacheLatencyMs?: number | null;
}

function VerdictBlock({
  verdict, tone, confidencePct, latencyMs, fast, hero,
  otpState, otpResult, otpLatencyMs, cached, cacheLatencyMs,
}: BlockProps) {
  const isReview = verdict === "review";
  return (
    <div
      data-testid="verdict-card"
      data-verdict={verdict}
      data-otp-state={otpState}
      data-cached={cached ? "true" : "false"}
      className={`verdict-reveal relative rounded-redis border bg-redis-bg-secondary p-6 ${tone.border} ${tone.glow}`}
    >
      {isReview ? (
        <ReviewBreadcrumb
          tone={tone}
          confidencePct={confidencePct}
          latencyMs={latencyMs}
          hero={hero}
          otpState={otpState}
          otpResult={otpResult}
          otpLatencyMs={otpLatencyMs}
        />
      ) : (
        <ApproveBlockBody
          tone={tone}
          confidencePct={confidencePct}
          latencyMs={latencyMs}
          fast={fast}
        />
      )}
      {cached && (
        <LangCacheVerdictSavings cacheLatencyMs={cacheLatencyMs} tokensSavedEstimate={2480} />
      )}
    </div>
  );
}

function ApproveBlockBody({
  tone, confidencePct, latencyMs, fast,
}: {
  tone: (typeof TONE)[keyof typeof TONE];
  confidencePct: number;
  latencyMs: number;
  fast: VerdictFastResponse | null;
}) {
  const signal = fast?.signals[0] ?? "";
  return (
    <>
      <div className="flex items-center gap-4">
        <div
          className={`flex h-16 min-w-[140px] items-center justify-center rounded-redis ${tone.bg} px-5 font-redis-body text-2xl font-bold text-white`}
        >
          {tone.label}
        </div>
        <div className="flex-1">
          <div className="font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted">
            Verdict · Confidence {confidencePct}%
          </div>
          <div className="mt-1 font-redis-body text-base leading-snug text-redis-text">
            {humanizeSignal(signal) || "Deterministic policy match."}
          </div>
          <div className="mt-2 font-redis-mono text-[11px] text-redis-text-muted">
            Decided in {latencyMs} ms · Redis-backed
          </div>
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted">
          <span>Confidence</span>
          <span>{confidencePct}%</span>
        </div>
        <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-redis-bg-tertiary">
          <div
            className={`h-full ${tone.bg}`}
            style={{ width: `${confidencePct}%` }}
            data-testid="confidence-bar"
          />
        </div>
      </div>

      {fast && (
        <div className="mt-4 font-redis-mono text-[11px] text-redis-text-muted">
          <span data-testid="verdict-fast-signals">
            signals: {fast.signals.join(", ") || "(none)"}
          </span>
        </div>
      )}
    </>
  );
}

function ReviewBreadcrumb({
  tone, confidencePct, latencyMs, hero, otpState, otpResult, otpLatencyMs,
}: {
  tone: (typeof TONE)[keyof typeof TONE];
  confidencePct: number;
  latencyMs: number;
  hero: HeroProfile | null;
  otpState: OtpState;
  otpResult: OtpConfirmResponse | null;
  otpLatencyMs: number;
}) {
  const last4 = hero?.cardLast4 ?? "0000";
  const device = "Sarah's iPhone";
  const subLine =
    otpState === "confirmed"
      ? `OTP confirmed via push to ${device}`
      : `Sending OTP to ····${last4}…`;
  const otpVisible = otpState === "confirmed";
  const approvedVisible = otpState === "confirmed";
  const otpSecs = otpVisible
    ? (otpLatencyMs > 0 ? (otpLatencyMs / 1000).toFixed(1) : "1.0")
    : "—";
  return (
    <div data-testid="verdict-breadcrumb">
      <div className="font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted">
        Verdict · Confidence {confidencePct}%
      </div>
      <ol className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-3">
        <li className="inline-flex items-center gap-2">
          <span
            data-testid="breadcrumb-reviewed"
            data-faded={approvedVisible ? "true" : "false"}
            className={`inline-flex h-11 min-w-[120px] items-center justify-center rounded-redis ${tone.bg} px-4 font-redis-body text-base font-bold text-white transition-opacity duration-500 ${
              approvedVisible ? "opacity-60" : "opacity-100"
            }`}
          >
            REVIEWED
          </span>
          {otpVisible && (
            <span aria-hidden className="font-redis-mono text-redis-text-muted">
              →
            </span>
          )}
        </li>
        {otpVisible && (
          <li className="inline-flex items-center gap-2">
            <span
              data-testid="breadcrumb-otp"
              className="verdict-reveal inline-flex h-11 items-center justify-center rounded-redis border border-verdict-review/60 bg-verdict-review/15 px-4 font-redis-body text-sm font-semibold text-verdict-review"
            >
              OTP confirmed ✓
            </span>
            {approvedVisible && (
              <span aria-hidden className="font-redis-mono text-redis-text-muted">
                →
              </span>
            )}
          </li>
        )}
        {approvedVisible && (
          <li className="inline-flex items-center gap-2">
            <span
              data-testid="breadcrumb-approved"
              className="verdict-reveal inline-flex h-11 min-w-[120px] items-center justify-center rounded-redis bg-verdict-approve px-4 font-redis-body text-base font-bold text-white shadow-[0_0_30px_-12px_rgba(31,179,107,0.7)]"
            >
              APPROVED
            </span>
          </li>
        )}
      </ol>
      <div
        data-testid="verdict-subline"
        className="mt-3 font-redis-body text-sm text-redis-text-secondary"
      >
        {subLine}
      </div>
      {approvedVisible && (
        <div
          data-testid="verdict-final-line"
          className="mt-2 font-redis-body text-base font-semibold text-redis-text"
        >
          Final: APPROVED via Step-Up Auth
        </div>
      )}
      <div className="mt-3 font-redis-mono text-[11px] text-redis-text-muted">
        Decided in {latencyMs} ms ·{" "}
        {otpVisible ? `OTP confirmed in ${otpSecs}s · ` : ""}
        Redis-backed
        {otpResult && otpResult.step_up_used && " · step_up_used=true"}
      </div>
    </div>
  );
}

function AnalystSummaryBlock({ score }: { score: ScoreResponse | null }) {
  const loading = !score;
  const latencySecs = score ? (score.trace.total_latency_ms / 1000).toFixed(1) : null;
  const llmModel = score?.trace.llm_model ?? "LLM";
  return (
    <div
      data-testid="analyst-summary-card"
      data-guide="analyst-summary"
      data-loading={loading ? "true" : "false"}
      className="rounded-redis border border-redis-border-secondary bg-redis-bg-tertiary/40 p-6"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted">
          Analyst summary
        </div>
        {!loading && (
          <div className="font-redis-mono text-[11px] text-redis-text-muted">
            LLM: {latencySecs}s · {llmModel}
          </div>
        )}
      </div>
      {loading ? (
        <div data-testid="analyst-summary-shimmer" className="mt-3 space-y-2">
          <div className="shimmer h-3 w-11/12 rounded" />
          <div className="shimmer h-3 w-10/12 rounded" />
          <div className="shimmer h-3 w-8/12 rounded" />
        </div>
      ) : (
        <Prose
          text={score!.reason}
          testId="analyst-summary-prose"
          className="mt-3 space-y-3 font-redis-body text-base leading-relaxed text-redis-text"
        />
      )}
      {!loading && (
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 font-redis-mono text-[11px] text-redis-text-muted">
          <span>steps: {score!.trace.steps.length}</span>
          <span>
            components:{" "}
            {Array.from(new Set(score!.trace.steps.map((s) => s.component))).join(", ")}
          </span>
        </div>
      )}
    </div>
  );
}

function humanizeSignal(raw: string): string {
  if (!raw) return "";
  // Render the most common verdict-fast signal strings as a readable reason.
  if (raw === "no_pending_review") {
    return "No pending review in flight — baseline approval.";
  }
  if (raw.startsWith("first_seen_device")) {
    return "First-seen device on a foreign transaction with no declared travel.";
  }
  if (raw.startsWith("impossible_travel_velocity")) {
    return "Impossible-travel velocity with no declared travel window.";
  }
  if (raw.startsWith("declared_travel_window_matches_merchant_country")) {
    return "Declared travel window matches merchant country — memory override approves.";
  }
  if (raw.startsWith("foreign_country")) {
    return "Foreign-country transaction.";
  }
  return raw;
}

