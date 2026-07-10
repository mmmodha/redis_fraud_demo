"use client";
import type { HeroProfile, TraceStep } from "@/lib/types";
import { IrisPanel, EmptyPanelState } from "../IrisPanel";
import { JsonTree } from "../JsonTree";
import { GUIDE_HIGHLIGHT_CLASS } from "@/lib/guidePanelHints";
import { useGuidePanelHints } from "@/lib/useGuidePanelHints";

export function AgentMemoryPanel({
  hero,
  steps,
}: {
  hero: HeroProfile | null;
  steps: TraceStep[];
}) {
  const { guideMode, hints } = useGuidePanelHints();
  const memHints = guideMode ? hints?.agentMemory : undefined;
  const memSteps = steps.filter((s) => s.component === "agent_memory");
  const memoryDoc = memSteps[0]?.output_data ?? null;
  const summary = memSteps[0]?.output_summary ?? "";
  const summaryFocus = memHints?.focusSummary === true;

  return (
    <IrisPanel
      title="Agent Memory"
      component="agent_memory"
      guideTarget="panel-agent-memory"
      subtitle={hero ? `mem:${hero.customer_id}` : "no customer selected"}
      badge={memSteps.length > 0 ? "Loaded" : "Idle"}
      active={memSteps.length > 0}
    >
      {!hero ? (
        <EmptyPanelState label="Select a hero to inspect memory." />
      ) : memoryDoc ? (
        <div data-testid="iris-memory-doc">
          <div
            className={`font-redis-mono text-[11px] ${
              summaryFocus
                ? `${GUIDE_HIGHLIGHT_CLASS} rounded px-2 py-1.5 font-semibold text-redis-text`
                : "text-redis-text-secondary"
            }`}
          >
            {summaryFocus && (
              <span className="mr-2 text-[9px] uppercase tracking-wider text-redis-hyper">
                Look here ·
              </span>
            )}
            {summary}
          </div>
          <div className="mt-2 rounded-redis border border-redis-border bg-redis-bg-tertiary p-2">
            <JsonTree
              data={memoryDoc}
              defaultOpen={!!memHints?.focusJsonKey}
              forceExpand={!!memHints?.focusJsonKey}
              highlightKeys={memHints?.focusJsonKey ? [memHints.focusJsonKey] : undefined}
            />
          </div>
        </div>
      ) : (
        <EmptyPanelState
          label={
            hero.key === "jane"
              ? "Run Jane's scenario to read mem:cust_jane (travel note)."
              : "Run scenario to read agent memory."
          }
        />
      )}
    </IrisPanel>
  );
}
