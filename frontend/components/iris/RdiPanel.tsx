"use client";
import { useEffect, useState } from "react";
import { getRdiStatus } from "@/lib/api";
import type { RdiStatus, TraceStep } from "@/lib/types";
import { IrisPanel, EmptyPanelState } from "../IrisPanel";

export function RdiPanel({ steps }: { steps: TraceStep[] }) {
  const [status, setStatus] = useState<RdiStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      const s = await getRdiStatus();
      if (!cancelled) setStatus(s);
    }
    poll();
    const id = setInterval(poll, 5_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const cdc = steps
    .filter((s) => s.redis_keys_touched && s.redis_keys_touched.length > 0)
    .flatMap((s) => s.redis_keys_touched.map((k) => ({ key: k, tool: s.tool })))
    .slice(0, 5);

  const lagMs = status?.lag_ms;
  const events = status?.events_total ?? 0;
  const lagDisplay =
    lagMs === null || lagMs === undefined
      ? { value: "Idle · caught up", tone: "good" as const }
      : lagMs < 100
      ? { value: `${lagMs} ms`, tone: "good" as const }
      : lagMs < 500
      ? { value: `${lagMs} ms`, tone: "warn" as const }
      : { value: `${lagMs} ms`, tone: "bad" as const };

  return (
    <IrisPanel
      title="RDI · Postgres → Redis"
      component="rdi"
      subtitle="Change-data capture sync"
      badge={status?.ok ? "Live" : status ? "No heartbeat" : "Probing"}
      active={!!status?.ok}
    >
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Events ingested" value={events.toLocaleString()} />
        <Stat label="Sync lag" value={lagDisplay.value} tone={lagDisplay.tone} />
      </div>

      <div className="mt-3">
        <div className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
          Last 5 keys touched
        </div>
        {cdc.length === 0 ? (
          <EmptyPanelState label="No CDC keys from the latest trace yet." />
        ) : (
          <ul className="mt-2 space-y-1" data-testid="iris-rdi-events">
            {cdc.map((c, i) => (
              <li
                key={`${c.key}-${i}`}
                className="trace-step-enter flex items-center justify-between gap-3 rounded-redis border border-redis-border bg-redis-bg-tertiary px-2.5 py-1.5 font-redis-mono text-[11px]"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <span className="truncate text-redis-text">{c.key}</span>
                <span className="text-redis-text-muted">{c.tool}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </IrisPanel>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" | "bad" }) {
  const color =
    tone === "good"
      ? "text-verdict-approve"
      : tone === "warn"
      ? "text-verdict-review"
      : tone === "bad"
      ? "text-verdict-block"
      : "text-redis-text";
  return (
    <div className="rounded-redis border border-redis-border bg-redis-bg-tertiary px-3 py-2">
      <div className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
        {label}
      </div>
      <div className={`mt-1 font-redis-mono text-lg ${color}`}>{value}</div>
    </div>
  );
}
