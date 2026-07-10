"use client";
import type { ReactNode } from "react";
import type { TraceComponent } from "@/lib/types";
import { COMPONENT_DOT } from "@/lib/traceColors";

interface Props {
  title: string;
  component: TraceComponent | "rdi";
  subtitle?: string;
  badge?: string;
  active?: boolean;
  guideTarget?: string;
  children: ReactNode;
}

export function IrisPanel({ title, component, subtitle, badge, active, guideTarget, children }: Props) {
  return (
    <section
      data-testid={`iris-panel-${component}`}
      data-guide={guideTarget}
      data-active={active ? "true" : "false"}
      className={`rounded-redis border bg-redis-bg-secondary p-4 transition-colors duration-200 ${
        active ? "border-redis-hyper" : "border-redis-border"
      }`}
    >
      <header className="flex items-center justify-between gap-3 border-b border-redis-border pb-3">
        <div className="flex items-center gap-2.5">
          <span className={`h-2.5 w-2.5 rounded-full ${COMPONENT_DOT[component] ?? "bg-redis-text-muted"}`} />
          <div>
            <div className="font-redis-body text-sm font-semibold leading-none">{title}</div>
            {subtitle && (
              <div className="mt-1 font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
                {subtitle}
              </div>
            )}
          </div>
        </div>
        {badge && (
          <span className="rounded-redis border border-redis-border bg-redis-bg-tertiary px-2 py-0.5 font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-secondary">
            {badge}
          </span>
        )}
      </header>
      <div className="mt-3 space-y-2 text-sm">{children}</div>
    </section>
  );
}

export function EmptyPanelState({ label }: { label: string }) {
  return (
    <div
      data-testid="iris-empty"
      className="rounded-redis border border-dashed border-redis-border p-3 font-redis-body text-xs text-redis-text-muted"
    >
      {label}
    </div>
  );
}
