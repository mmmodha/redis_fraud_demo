"use client";
import type { HeroProfile, TraceStep } from "@/lib/types";
import { IrisPanel, EmptyPanelState } from "../IrisPanel";
import { JsonTree } from "../JsonTree";

export function AgentMemoryPanel({
  hero,
  steps,
}: {
  hero: HeroProfile | null;
  steps: TraceStep[];
}) {
  const memSteps = steps.filter((s) => s.component === "agent_memory");
  const memoryDoc = memSteps[0]?.output_data ?? null;

  return (
    <IrisPanel
      title="Agent Memory"
      component="agent_memory"
      subtitle={hero ? `mem:${hero.customer_id}` : "no customer selected"}
      badge={memSteps.length > 0 ? "Loaded" : "Idle"}
      active={memSteps.length > 0}
    >
      {!hero ? (
        <EmptyPanelState label="Select a hero to inspect memory." />
      ) : memoryDoc ? (
        <div data-testid="iris-memory-doc">
          <div className="font-redis-mono text-[11px] text-redis-text-secondary">
            {memSteps[0]?.output_summary}
          </div>
          <div className="mt-2 rounded-redis border border-redis-border bg-redis-bg-tertiary p-2">
            <JsonTree data={memoryDoc} defaultOpen />
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
