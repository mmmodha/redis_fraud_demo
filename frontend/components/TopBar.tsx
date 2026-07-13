"use client";
import { useEffect, useState } from "react";
import { checkHealth, clearDemoCache } from "@/lib/api";
import { DEMO_UI_RESET_EVENT } from "@/lib/demoEvents";
import { IrisDiagramModal } from "./IrisDiagramModal";
import { useDemoGuide } from "./DemoGuideProvider";

// Wave 7n: presenter "Clear cache" also resets hero verdict UI state.
export const CACHE_CLEARED_EVENT = DEMO_UI_RESET_EVENT;

export function TopBar() {
  const [live, setLive] = useState<boolean | null>(null);
  const [irisModalOpen, setIrisModalOpen] = useState(false);
  const [clearState, setClearState] = useState<"idle" | "clearing" | "done">("idle");
  const { guideMode, setGuideMode } = useDemoGuide();
  const showCacheClear = process.env.NEXT_PUBLIC_DEMO_CACHE_CLEAR === "true";

  async function onClearCache() {
    if (clearState === "clearing") return;
    setClearState("clearing");
    try {
      await clearDemoCache();
    } catch {
      // Best-effort; UI still resets so the presenter can move on.
    }
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(DEMO_UI_RESET_EVENT));
    }
    setClearState("done");
    setTimeout(() => setClearState("idle"), 1500);
  }

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      const ok = await checkHealth();
      if (!cancelled) setLive(ok);
    }
    poll();
    const id = setInterval(poll, 10_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <header className="sticky top-0 z-30 border-b border-redis-border bg-redis-bg/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center gap-6 px-8 py-4">
        <div className="flex items-center gap-3">
          <img
            src="/redis-mark.png"
            alt="Redis"
            className="h-8 w-8 rounded-redis"
          />
          <div>
            <div className="font-redis-body text-lg font-semibold leading-none">
              Redis Bank Fraud Command Center
            </div>
            <div className="font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted">
              Redis IRIS · Live demo
            </div>
          </div>
        </div>

        <div className="flex-1" />

        <div
          className="flex items-center gap-2 font-redis-mono text-xs uppercase tracking-wider"
          data-testid="live-indicator"
          data-live={live === true ? "true" : live === false ? "false" : "pending"}
        >
          <span
            className={`live-dot inline-block h-2.5 w-2.5 rounded-full ${
              live === true
                ? "bg-verdict-approve"
                : live === false
                ? "bg-verdict-block"
                : "bg-redis-text-muted"
            }`}
          />
          <span className="text-redis-text-secondary">
            {live === true ? "Backend live" : live === false ? "Backend down" : "Checking…"}
          </span>
        </div>

        {process.env.NEXT_PUBLIC_CONTEXT_RETRIEVER_URL && (
          <a
            href={process.env.NEXT_PUBLIC_CONTEXT_RETRIEVER_URL}
            target="_blank"
            rel="noreferrer"
            title="Opens your Context Retriever surface in a new tab — where this demo pulls customer + transaction context"
            className="font-redis-body text-sm font-medium text-redis-text-link hover:text-redis-hyper hover:underline"
          >
            Context Retriever ↗
          </a>
        )}
        <button
          type="button"
          onClick={() => setGuideMode(!guideMode)}
          data-testid="guide-mode-toggle"
          title="Step-by-step guided demo with highlights"
          className={`font-redis-body text-sm font-medium hover:underline ${
            guideMode ? "text-redis-hyper" : "text-redis-text-link hover:text-redis-hyper"
          }`}
        >
          {guideMode ? "Guide on" : "Guide mode"}
        </button>
        <button
          type="button"
          onClick={() => setIrisModalOpen(true)}
          title="Show the audience the 4 animated Redis IRIS architecture diagrams"
          className="font-redis-body text-sm font-medium text-redis-text-link hover:text-redis-hyper hover:underline"
        >
          How IRIS works ↗
        </button>
        <a
          href={process.env.NEXT_PUBLIC_REDIS_CLOUD_URL || "https://app.redislabs.com/"}
          target="_blank"
          rel="noreferrer"
          title="Opens your Redis Cloud subscription in a new tab"
          className="font-redis-body text-sm font-medium text-redis-text-link hover:text-redis-hyper hover:underline"
        >
          Redis Cloud Console ↗
        </a>
        {process.env.NEXT_PUBLIC_GITHUB_URL && (
          <a
            href={process.env.NEXT_PUBLIC_GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            title="Open this demo's repo on GitHub"
            className="font-redis-body text-sm font-medium text-redis-text-link hover:text-redis-hyper hover:underline"
          >
            GitHub ↗
          </a>
        )}
        {showCacheClear && (
          <button
            type="button"
            onClick={onClearCache}
            disabled={clearState === "clearing"}
            data-testid="clear-cache-button"
            title="Clear the Redis verdict cache so the next hero run goes through the full agent again."
            className="font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted hover:text-redis-text-secondary disabled:opacity-50"
          >
            {clearState === "clearing"
              ? "Clearing…"
              : clearState === "done"
                ? "Cache cleared ✓"
                : "Clear cache"}
          </button>
        )}
      </div>
      <IrisDiagramModal open={irisModalOpen} onClose={() => setIrisModalOpen(false)} />
    </header>
  );
}
