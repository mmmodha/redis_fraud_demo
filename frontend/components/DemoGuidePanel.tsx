"use client";

import { useState } from "react";
import { useDemoGuide } from "./DemoGuideProvider";
import { GuideIrisDiagram } from "./GuideIrisDiagram";
import { GUIDE_STEPS, isGuideCacheReplayStep, isGuideHeroRunEventStep, type HeroKey } from "@/lib/demoGuide";
import { copyToClipboard } from "@/lib/clipboard";

export function DemoGuidePanel() {
  const {
    guideMode,
    setGuideMode,
    currentStep,
    currentStepIndex,
    continueStep,
    goBackStep,
    skipStep,
    resetGuide,
    runHeroForGuide,
    insertChatMessage,
    scoreReadyForHero,
    otpConfirmedForSarah,
    cacheHitForHero,
    isScoringHero,
    isChatLoading,
  } = useDemoGuide();

  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "manual">("idle");

  if (!guideMode || !currentStep) return null;

  const step = currentStep;
  const isManual = step.advance.mode === "manual";
  const requiresScore =
    step.advance.mode === "manual" && step.advance.requiresScore === true;
  const requiresOtp =
    step.advance.mode === "manual" && step.advance.requiresOtp === true;

  const requiresCacheHit =
    step.advance.mode === "manual" && step.advance.requiresCacheHit === true;

  const scoreReady =
    !requiresScore || (step.hero != null && scoreReadyForHero === step.hero);
  const otpReady = !requiresOtp || otpConfirmedForSarah;
  const cacheReady =
    !requiresCacheHit || (step.hero != null && cacheHitForHero === step.hero);

  const scoringActive = isScoringHero != null;
  const runStepComplete =
    isGuideHeroRunEventStep(step) &&
    step.hero != null &&
    scoreReadyForHero === step.hero;
  const cacheReplayComplete =
    isGuideCacheReplayStep(step) &&
    step.hero != null &&
    cacheHitForHero === step.hero;
  const canContinue =
    (isManual && scoreReady && otpReady && cacheReady && !scoringActive) ||
    runStepComplete ||
    cacheReplayComplete;

  const thinkingMessage = scoringActive
    ? "Running scenario — Redis is assembling context…"
    : isChatLoading
      ? "Chatbot is thinking — both sides are answering…"
      : requiresScore && !scoreReady
        ? "Waiting for analyst summary to finish loading…"
        : requiresOtp && !otpReady
          ? "Waiting for OTP confirmation…"
          : requiresCacheHit && !cacheReady
            ? "Waiting for LangCache replay on the verdict card…"
            : null;

  async function handleCopySuggested() {
    if (!step.suggestedText) return;
    const result = await copyToClipboard(step.suggestedText);
    setCopyStatus(result === "manual" ? "manual" : "copied");
    setTimeout(() => setCopyStatus("idle"), 3000);
  }

  function handleInsertChat() {
    if (!step.suggestedText) return;
    insertChatMessage(step.suggestedText);
  }

  function handleRunHero() {
    const hero = step.hero ?? step.activateHero;
    if (hero) runHeroForGuide(hero as HeroKey);
  }

  return (
    <aside
      data-testid="demo-guide-panel"
      className="fixed right-0 top-[73px] z-40 flex h-[calc(100vh-73px)] w-[min(400px,35vw)] max-xl:w-[340px] flex-col border-l border-redis-border bg-redis-bg-secondary shadow-[-8px_0_24px_rgba(0,0,0,0.35)]"
    >
      <div className="flex items-center justify-between border-b border-redis-border px-4 py-3">
        <div>
          <div className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-hyper">
            Guide mode
          </div>
          <div className="font-redis-body text-sm font-semibold text-redis-text">
            Step {currentStepIndex + 1} of {GUIDE_STEPS.length}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setGuideMode(false)}
          className="font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted hover:text-redis-text"
        >
          Close
        </button>
      </div>

      {thinkingMessage && (
        <div
          data-testid="guide-thinking-banner"
          className="border-b border-redis-hyper/30 bg-redis-hyper/10 px-4 py-3"
        >
          <p className="font-redis-body text-sm font-semibold text-redis-hyper animate-pulse">
            {thinkingMessage}
          </p>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <h2 className="font-redis-body text-lg font-bold text-redis-text">
          {step.title}
        </h2>
        <p className="mt-3 font-redis-body text-sm leading-relaxed text-redis-text-secondary">
          {step.instruction}
        </p>

        {step.redisBenefit && (
          <div className="mt-4 rounded-redis border border-redis-hyper/30 bg-redis-hyper/5 px-3 py-2">
            <div className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-hyper">
              Why Redis
            </div>
            <p className="mt-1 font-redis-body text-xs leading-relaxed text-redis-text-secondary">
              {step.redisBenefit}
            </p>
          </div>
        )}

        {step.irisDiagram && <GuideIrisDiagram slug={step.irisDiagram} />}

        {step.summaryItems && step.summaryItems.length > 0 && (
          <ul className="mt-4 space-y-2" data-testid="guide-summary-list">
            {step.summaryItems.map((item) => (
              <li
                key={item}
                className="flex gap-2 rounded-redis border border-redis-border bg-redis-bg-tertiary px-3 py-2 font-redis-body text-xs leading-relaxed text-redis-text-secondary"
              >
                <span className="shrink-0 text-redis-hyper">✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}

        {step.presenterLine && (
          <blockquote className="mt-4 rounded-redis border border-l-[4px] border-l-redis-hyper border-redis-border bg-redis-bg-tertiary px-3 py-2 font-redis-body text-sm italic text-redis-text-link">
            &ldquo;{step.presenterLine}&rdquo;
          </blockquote>
        )}

        {step.suggestedAction === "type-message" && step.suggestedText && (
          <div className="mt-4 rounded-redis border border-verdict-approve/40 bg-verdict-approve/10 px-3 py-2">
            <div className="font-redis-mono text-[10px] uppercase tracking-wider text-verdict-approve">
              Type this
            </div>
            <p className="mt-1 font-redis-body text-sm font-semibold text-redis-text">
              {step.suggestedText}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                data-testid="guide-insert-chat"
                onClick={handleInsertChat}
                className="rounded-redis bg-redis-hyper px-3 py-1.5 font-redis-body text-xs font-semibold text-white hover:opacity-90"
              >
                Insert into chat
              </button>
              <button
                type="button"
                data-testid="guide-copy-suggested"
                onClick={handleCopySuggested}
                className="rounded-redis border border-redis-border bg-redis-bg-tertiary px-3 py-1.5 font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-link hover:text-redis-hyper"
              >
                {copyStatus === "copied"
                  ? "Copied!"
                  : copyStatus === "manual"
                    ? "Select text & press Ctrl+C / Cmd+C"
                    : "Copy to clipboard"}
              </button>
            </div>
            <p className="mt-2 font-redis-body text-[11px] leading-snug text-redis-text-muted">
              Then press Enter or click Ask both to send.
            </p>
          </div>
        )}
      </div>

      <div className="space-y-2 border-t border-redis-border px-4 py-3">
        {step.suggestedAction === "run-hero" && (
          <button
            type="button"
            data-testid="guide-run-hero"
            onClick={handleRunHero}
            disabled={scoringActive}
            className="w-full rounded-redis bg-redis-hyper px-3 py-2.5 font-redis-body text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60"
          >
            {scoringActive
              ? "Running scenario…"
              : runStepComplete || cacheReplayComplete
                ? "Run again"
                : "Run scenario"}
          </button>
        )}

        {step.suggestedAction === "close-guide" ? (
          <button
            type="button"
            data-testid="guide-finish"
            onClick={() => setGuideMode(false)}
            className="w-full rounded-redis bg-redis-hyper px-3 py-2.5 font-redis-body text-sm font-semibold text-white hover:opacity-90"
          >
            Finish tour
          </button>
        ) : (
          canContinue && (
            <button
              type="button"
              data-testid="guide-continue"
              onClick={continueStep}
              className="w-full rounded-redis bg-redis-hyper px-3 py-2.5 font-redis-body text-sm font-semibold text-white hover:opacity-90"
            >
              {runStepComplete || cacheReplayComplete ? "Continue without re-running" : "Continue"}
            </button>
          )
        )}

        <div className="flex gap-2">
          {currentStepIndex > 0 && (
            <button
              type="button"
              data-testid="guide-back"
              onClick={goBackStep}
              className="flex-1 rounded-redis border border-redis-border bg-redis-bg-tertiary px-3 py-2 font-redis-body text-xs font-semibold text-redis-text-secondary hover:bg-redis-border"
            >
              Back
            </button>
          )}
          {step.suggestedAction !== "close-guide" && (
            <button
              type="button"
              onClick={skipStep}
              className="flex-1 rounded-redis border border-redis-border bg-redis-bg-tertiary px-3 py-2 font-redis-body text-xs font-semibold text-redis-text-secondary hover:bg-redis-border"
            >
              Skip step
            </button>
          )}
          <button
            type="button"
            onClick={resetGuide}
            className={`rounded-redis border border-redis-border px-3 py-2 font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted hover:text-redis-text ${
              step.suggestedAction === "close-guide" ? "flex-1" : ""
            }`}
          >
            Restart
          </button>
        </div>
      </div>

      <div className="px-4 pb-4">
        <div className="h-1.5 overflow-hidden rounded-full bg-redis-bg-tertiary">
          <div
            className="h-full bg-redis-hyper transition-all duration-300"
            style={{
              width: `${((currentStepIndex + 1) / GUIDE_STEPS.length) * 100}%`,
            }}
          />
        </div>
      </div>
    </aside>
  );
}
