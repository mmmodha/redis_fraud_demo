"use client";
import { useEffect, useState } from "react";
import { getFeatures } from "@/lib/api";
import type { HeroProfile, TraceStep } from "@/lib/types";
import { IrisPanel, EmptyPanelState } from "../IrisPanel";
import { GUIDE_HIGHLIGHT_CLASS } from "@/lib/guidePanelHints";
import { useGuidePanelHints } from "@/lib/useGuidePanelHints";

export function FeatureStorePanel({
  hero,
  steps,
}: {
  hero: HeroProfile | null;
  steps: TraceStep[];
}) {
  const { guideMode, hints } = useGuidePanelHints();
  const focusTrace = guideMode ? hints?.featureStore?.focusTraceContains : undefined;
  const [fallback, setFallback] = useState<Record<string, unknown> | null>(null);

  const fsSteps = steps.filter((s) => s.component === "feature_store");

  useEffect(() => {
    let cancelled = false;
    setFallback(null);
    if (!hero) return;
    if (fsSteps.length > 0) return;
    async function load() {
      const f = await getFeatures(hero!.card_id);
      if (!cancelled) setFallback(f);
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hero?.card_id, fsSteps.length]);

  const features = fsSteps[0]?.output_data ?? fallback ?? null;

  return (
    <IrisPanel
      title="Feature Store"
      component="feature_store"
      guideTarget="panel-feature-store"
      subtitle={hero ? `card:${hero.card_id}` : "no card selected"}
      badge={fsSteps.length > 0 ? "From trace" : fallback ? "Live fetch" : "Idle"}
      active={fsSteps.length > 0}
    >
      {!hero ? (
        <EmptyPanelState label="Select a hero to see their features." />
      ) : features ? (
        <ul className="space-y-1" data-testid="iris-feature-items">
          {Object.entries(features).map(([k, v]) => (
            <li
              key={k}
              className="flex items-center justify-between gap-3 rounded-redis border border-redis-border bg-redis-bg-tertiary px-2.5 py-1.5 font-redis-mono text-[11px]"
            >
              <span className="text-redis-text-muted">{k}</span>
              <span className="text-redis-text">{formatValue(v)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyPanelState label="Run a scenario to populate features." />
      )}

      {fsSteps.length > 0 && (
        <div className="mt-3 font-redis-mono text-[11px] text-redis-text-secondary">
          {fsSteps.map((s, i) => {
            const isFocus =
              focusTrace != null &&
              s.output_summary.toLowerCase().includes(focusTrace.toLowerCase());
            return (
              <div
                key={`${s.tool}-${i}`}
                className={`trace-step-enter rounded-redis border px-2 py-1.5 ${
                  isFocus
                    ? `${GUIDE_HIGHLIGHT_CLASS} border-redis-hyper`
                    : "border-redis-border bg-redis-bg-tertiary"
                }`}
                style={{ animationDelay: `${i * 80}ms` }}
              >
                {isFocus && (
                  <span className="mr-2 text-[9px] uppercase tracking-wider text-redis-hyper">
                    Look here ·
                  </span>
                )}
                <span className="text-redis-text-muted">{s.tool}</span> · {s.latency_ms} ms ·{" "}
                <span className={isFocus ? "font-semibold text-redis-text" : "text-redis-text"}>
                  {s.output_summary}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </IrisPanel>
  );
}

function formatValue(v: unknown): string {
  if (typeof v === "number") {
    return Number.isInteger(v) ? String(v) : v.toFixed(2);
  }
  if (typeof v === "boolean") return v ? "true" : "false";
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
