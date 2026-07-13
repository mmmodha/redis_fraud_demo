"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { HEROES } from "@/lib/heroes";
import type { HeroKey } from "@/lib/demoGuide";
import type {
  HeroProfile,
  OtpConfirmResponse,
  ScoreResponse,
  TraceStep,
  VerdictFastResponse,
} from "@/lib/types";
import { confirmOtp, fetchVerdictFast, scoreHeroStream } from "@/lib/api";
import { mockScoreStream } from "@/lib/mock";
import { HeroCard } from "./HeroCard";
import { CACHE_CLEARED_EVENT } from "./TopBar";
import { VerdictCard, type OtpState } from "./VerdictCard";
import { RdiPanel } from "./iris/RdiPanel";
import { FeatureStorePanel } from "./iris/FeatureStorePanel";
import { ContextRetrieverPanel } from "./iris/ContextRetrieverPanel";
import { AgentMemoryPanel } from "./iris/AgentMemoryPanel";
import { ChatbotCompare } from "./ChatbotCompare";
import { useDemoGuideOptional } from "./DemoGuideProvider";
import { useGuidePanelHints } from "@/lib/useGuidePanelHints";
import { GUIDE_HIGHLIGHT_CLASS } from "@/lib/guidePanelHints";
import { isGuideRunStepForHero } from "@/lib/demoGuide";

export function CommandCenter() {
  const [activeKey, setActiveKey] = useState<HeroProfile["key"]>(HEROES[0].key);
  const [scores, setScores] = useState<Record<string, ScoreResponse | null>>({});
  const [fastVerdicts, setFastVerdicts] = useState<
    Record<string, VerdictFastResponse | null>
  >({});
  const [runIds, setRunIds] = useState<Record<string, number>>({});
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [stepsByCustomer, setStepsByCustomer] = useState<Record<string, TraceStep[]>>({});
  const [thinkingByCustomer, setThinkingByCustomer] = useState<Record<string, boolean>>({});
  const [otpStates, setOtpStates] = useState<Record<string, OtpState>>({});
  const [otpResults, setOtpResults] = useState<
    Record<string, OtpConfirmResponse | null>
  >({});
  const [otpLatencyMs, setOtpLatencyMs] = useState<Record<string, number>>({});
  const otpFiredFor = useRef<Set<string>>(new Set());
  const runHeroRef = useRef<(hero: HeroProfile, bypassCache?: boolean) => Promise<void>>(
    async () => {},
  );
  const guide = useDemoGuideOptional();

  const activeHero = HEROES.find((h) => h.key === activeKey) ?? null;
  const activeScore = activeHero ? scores[activeHero.customer_id] ?? null : null;
  const activeFast = activeHero ? fastVerdicts[activeHero.customer_id] ?? null : null;
  const activeRunId = activeHero ? runIds[activeHero.customer_id] ?? 0 : 0;
  const activeOtpState = activeHero ? otpStates[activeHero.customer_id] ?? "idle" : "idle";
  const activeOtpResult = activeHero ? otpResults[activeHero.customer_id] ?? null : null;
  const activeOtpLatency = activeHero ? otpLatencyMs[activeHero.customer_id] ?? 0 : 0;
  const visibleSteps = activeHero
    ? stepsByCustomer[activeHero.customer_id] ?? []
    : [];
  const activeThinking = activeHero
    ? thinkingByCustomer[activeHero.customer_id] ?? false
    : false;

  useEffect(() => {
    if (!guide) return;
    guide.registerRunHero((key: HeroKey) => {
      const h = HEROES.find((x) => x.key === key);
      if (h) void runHeroRef.current(h);
    });
    guide.registerSelectHero((key: HeroKey) => setActiveKey(key));
  }, [guide]);

  useEffect(() => {
    if (!activeHero || activeOtpState !== "confirmed") return;
    if (activeHero.key !== "sarah") return;
    guide?.setOtpConfirmedForSarah(true);
    guide?.completeAction({ type: "otp-confirmed", hero: "sarah" });
  }, [activeHero, activeOtpState, guide]);

  useEffect(() => {
    if (!activeHero || !activeScore) return;
    guide?.setScoreReadyForHero(activeHero.key);
    guide?.completeAction({ type: "score-complete", hero: activeHero.key });
  }, [activeHero, activeScore, guide]);

  useEffect(() => {
    if (!activeHero || !activeFast) return;
    if (activeFast.verdict !== "review") return;
    const cid = activeHero.customer_id;
    if (otpFiredFor.current.has(cid)) return;
    otpFiredFor.current.add(cid);
    setOtpStates((prev) => ({ ...prev, [cid]: "sending" }));
    const txId = `tx_${cid}_pending`;
    const otpStart = performance.now();
    const timer = setTimeout(() => {
      confirmOtp(txId)
        .catch(
          () =>
            ({
              confirmed: true,
              final_verdict: "approve",
              step_up_used: true,
            }) as OtpConfirmResponse,
        )
        .then((result) => {
          const elapsed = Math.round(performance.now() - otpStart);
          setOtpResults((prev) => ({ ...prev, [cid]: result }));
          setOtpLatencyMs((prev) => ({ ...prev, [cid]: elapsed }));
          setOtpStates((prev) => ({ ...prev, [cid]: "confirmed" }));
        });
    }, 1000);
    return () => clearTimeout(timer);
  }, [activeHero, activeFast]);

  useEffect(() => {
    function onCleared() {
      setScores({});
      setFastVerdicts({});
      setStepsByCustomer({});
      setThinkingByCustomer({});
      setOtpStates({});
      setOtpResults({});
      setOtpLatencyMs({});
      otpFiredFor.current.clear();
      guide?.setScoreReadyForHero(null);
      guide?.setCacheHitForHero(null);
      guide?.setOtpConfirmedForSarah(false);
    }
    window.addEventListener(CACHE_CLEARED_EVENT, onCleared);
    return () => window.removeEventListener(CACHE_CLEARED_EVENT, onCleared);
  }, [guide]);

  const runHero = useCallback(async (hero: HeroProfile, bypassCache: boolean = false) => {
    setLoadingKey(hero.key);
    setActiveKey(hero.key);
    guide?.setScoreReadyForHero(null);
    guide?.setCacheHitForHero(null);
    guide?.setIsScoringHero(hero.key);
    if (hero.key === "sarah") guide?.setOtpConfirmedForSarah(false);
    setScores((prev) => ({ ...prev, [hero.customer_id]: null }));
    setFastVerdicts((prev) => ({ ...prev, [hero.customer_id]: null }));
    setStepsByCustomer((prev) => ({ ...prev, [hero.customer_id]: [] }));
    setThinkingByCustomer((prev) => ({ ...prev, [hero.customer_id]: false }));
    setOtpStates((prev) => ({ ...prev, [hero.customer_id]: "idle" }));
    setOtpResults((prev) => ({ ...prev, [hero.customer_id]: null }));
    setOtpLatencyMs((prev) => ({ ...prev, [hero.customer_id]: 0 }));
    otpFiredFor.current.delete(hero.customer_id);
    setRunIds((prev) => ({
      ...prev,
      [hero.customer_id]: (prev[hero.customer_id] ?? 0) + 1,
    }));

    const fastPromise = fetchVerdictFast(hero).catch(
      () =>
        ({
          verdict: hero.expectedVerdict,
          confidence: 0.9,
          signals: ["mock_fast_path"],
          total_latency_ms: 0,
        }) as VerdictFastResponse,
    );
    fastPromise.then((fast) =>
      setFastVerdicts((prev) => ({ ...prev, [hero.customer_id]: fast })),
    );

    const handlers = {
      onThinking: () =>
        setThinkingByCustomer((prev) => ({ ...prev, [hero.customer_id]: true })),
      onStep: (step: TraceStep) => {
        setThinkingByCustomer((prev) => ({ ...prev, [hero.customer_id]: false }));
        setStepsByCustomer((prev) => ({
          ...prev,
          [hero.customer_id]: [...(prev[hero.customer_id] ?? []), step],
        }));
        guide?.completeAction({
          type: "trace-component",
          hero: hero.key,
          component: step.component,
        });
      },
      onFinal: (resp: ScoreResponse) => {
        setScores((prev) => ({ ...prev, [hero.customer_id]: resp }));
        setThinkingByCustomer((prev) => ({ ...prev, [hero.customer_id]: false }));
        guide?.setScoreReadyForHero(hero.key);
        guide?.completeAction({ type: "score-complete", hero: hero.key });
        guide?.completeAction({ type: "hero-run", hero: hero.key });
        if (resp.cached) {
          guide?.setCacheHitForHero(hero.key);
          guide?.completeAction({ type: "hero-cache-hit", hero: hero.key });
        }
      },
    };
    try {
      await scoreHeroStream(hero, handlers, undefined, { bypassCache });
    } catch {
      await mockScoreStream(hero.customer_id, handlers);
    }
    setLoadingKey(null);
    guide?.setIsScoringHero(null);
  }, [guide]);

  runHeroRef.current = runHero;

  return (
    <div
      className={`mx-auto max-w-[1600px] px-8 py-8 ${
        guide?.guideMode ? "pr-[min(400px,35vw)] max-xl:pr-[340px]" : ""
      }`}
    >
      <section>
        <h1 className="font-redis-body text-3xl font-bold tracking-tight">
          Pick a customer. Watch Redis IRIS decide.
        </h1>
        <p className="mt-2 max-w-3xl font-redis-body text-base text-redis-text-secondary">
          Four customer scenarios across the bank — decision and reasoning in milliseconds,
          powered by Redis.
        </p>
      </section>

      <section
        className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-2 wide:grid-cols-4"
        data-testid="hero-grid"
        data-guide="hero-grid"
      >
        {HEROES.map((h) => (
          <HeroCard
            key={h.key}
            hero={h}
            active={activeKey === h.key}
            loading={loadingKey === h.key}
            verdict={fastVerdicts[h.customer_id]?.verdict ?? scores[h.customer_id]?.verdict ?? null}
            guideHideRun={
              guide?.guideMode === true &&
              isGuideRunStepForHero(guide.currentStep, h.key)
            }
            onSelect={() => {
              setActiveKey(h.key);
              guide?.completeAction({ type: "hero-select", hero: h.key });
            }}
            onRun={(bypassCache) => runHero(h, bypassCache)}
          />
        ))}
      </section>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <VerdictCard
            fast={activeFast}
            score={activeScore}
            hero={activeHero}
            otpState={activeOtpState}
            otpResult={activeOtpResult}
            otpLatencyMs={activeOtpLatency}
          />
          <TraceStrip steps={visibleSteps} thinking={activeThinking} />
          <ChatbotCompare
            key={activeHero ? `${activeHero.customer_id}:${activeRunId}` : "none"}
            hero={activeHero}
          />
        </div>

        <aside className="space-y-4" data-testid="iris-rail">
          <RdiPanel steps={visibleSteps} />
          <FeatureStorePanel hero={activeHero} steps={visibleSteps} />
          <ContextRetrieverPanel steps={visibleSteps} />
          <AgentMemoryPanel hero={activeHero} steps={visibleSteps} />
        </aside>
      </div>
    </div>
  );
}

function TraceStrip({ steps, thinking }: { steps: TraceStep[]; thinking: boolean }) {
  const { guideMode, hints } = useGuidePanelHints();
  const traceHints = guideMode ? hints?.traceStrip : undefined;
  if (steps.length === 0 && !thinking) return null;
  return (
    <section
      data-testid="trace-strip"
      data-guide="trace-strip"
      className="rounded-redis border border-redis-border bg-redis-bg-secondary p-4"
    >
      <div className="font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted">
        Agent trace · {steps.length} step{steps.length === 1 ? "" : "s"}
      </div>
      <ol className="mt-2 flex flex-wrap items-center gap-2">
        {steps.map((s, i) => {
          const focusComponent = traceHints?.focusComponent;
          const highlighted = focusComponent != null && s.component === focusComponent;
          return (
            <li
              key={i}
              className={`trace-step-enter inline-flex items-center gap-2 rounded-redis border px-2.5 py-1.5 font-redis-mono text-[11px] ${
                highlighted
                  ? `${GUIDE_HIGHLIGHT_CLASS} border-redis-hyper`
                  : "border-redis-border bg-redis-bg-tertiary"
              }`}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <span className="text-redis-text-link">{i + 1}</span>
              <span className={highlighted ? "font-semibold text-redis-hyper" : "text-redis-text"}>
                {s.component}
              </span>
              <span className="text-redis-text-muted">·</span>
              <span className="text-redis-text-secondary">{s.tool}</span>
              <span className="text-redis-text-muted">{s.latency_ms}ms</span>
            </li>
          );
        })}
        {thinking && (
          <li
            data-testid="trace-thinking"
            className="inline-flex items-center gap-2 rounded-redis border border-redis-border bg-redis-bg-tertiary px-2.5 py-1.5 font-redis-mono text-[11px] text-redis-text-secondary animate-pulse"
          >
            <span className="text-redis-text-link">●</span>
            <span>LLM is reasoning…</span>
          </li>
        )}
      </ol>
    </section>
  );
}
