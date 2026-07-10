"use client";
import { useEffect, useState } from "react";
import type { TraceStep } from "@/lib/types";
import { IrisPanel, EmptyPanelState } from "../IrisPanel";
import { JsonTree } from "../JsonTree";
import { GUIDE_HIGHLIGHT_CLASS } from "@/lib/guidePanelHints";
import { useGuidePanelHints } from "@/lib/useGuidePanelHints";

export function ContextRetrieverPanel({ steps }: { steps: TraceStep[] }) {
  const { guideMode, hints } = useGuidePanelHints();
  const focusTool = guideMode ? hints?.contextRetriever?.focusTool : undefined;
  const calls = steps.filter((s) => s.component === "context_retriever");
  return (
    <IrisPanel
      title="Context Retriever"
      component="context_retriever"
      guideTarget="panel-context-retriever"
      subtitle="Auto-generated tool calls"
      badge={`${calls.length} call${calls.length === 1 ? "" : "s"}`}
      active={calls.length > 0}
    >
      {calls.length === 0 ? (
        <EmptyPanelState label="Run a scenario to see tool calls." />
      ) : (
        <ul className="space-y-2" data-testid="iris-context-items">
          {calls.map((s, i) => (
            <ContextRow
              key={`${s.tool}-${i}`}
              step={s}
              index={i}
              focusTool={focusTool}
              guideMode={guideMode}
            />
          ))}
        </ul>
      )}
    </IrisPanel>
  );
}

function ContextRow({
  step,
  index,
  focusTool,
  guideMode,
}: {
  step: TraceStep;
  index: number;
  focusTool: string | undefined;
  guideMode: boolean;
}) {
  const isFocus = guideMode && focusTool != null && step.tool === focusTool;
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (isFocus) setOpen(true);
    if (!guideMode) setOpen(false);
  }, [isFocus, guideMode, step.tool]);

  return (
    <li
      className={`trace-step-enter rounded-redis border bg-redis-bg-tertiary ${
        isFocus ? `${GUIDE_HIGHLIGHT_CLASS} border-redis-hyper` : "border-redis-border"
      }`}
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-3 px-2.5 py-2 text-left"
      >
        <div className="min-w-0 flex-1">
          <div className={`font-redis-mono text-[11px] ${isFocus ? "font-semibold text-redis-hyper" : "text-redis-text"}`}>
            {step.tool}
            {isFocus && (
              <span className="ml-2 rounded bg-redis-hyper/20 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-redis-hyper">
                Look here
              </span>
            )}
          </div>
          <div className={`truncate font-redis-body text-[12px] ${isFocus ? "font-medium text-redis-text" : "text-redis-text-secondary"}`}>
            {step.output_summary}
          </div>
        </div>
        <span className="shrink-0 font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
          {step.latency_ms} ms {open ? "▲" : "▼"}
        </span>
      </button>
      {open && (
        <div className="max-h-72 min-w-0 max-w-full space-y-2 overflow-hidden overflow-y-auto border-t border-redis-border bg-redis-bg-secondary px-2.5 py-2">
          <div>
            <div className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
              Input
            </div>
            <JsonTree data={step.input} defaultOpen={isFocus} forceExpand={isFocus} />
          </div>
          {step.output_data && (
            <div>
              <div className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
                Output
              </div>
              <JsonTree data={step.output_data} defaultOpen={isFocus} forceExpand={isFocus} />
            </div>
          )}
          {step.redis_keys_touched.length > 0 && (
            <div>
              <div className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
                Redis keys
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {step.redis_keys_touched.map((k) => (
                  <span
                    key={k}
                    className="rounded-redis border border-redis-border bg-redis-bg-tertiary px-1.5 py-0.5 font-redis-mono text-[10px] text-redis-text-link"
                  >
                    {k}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </li>
  );
}
