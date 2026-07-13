import type { GuideStep } from "./demoGuide";

/** One focal highlight per panel — keeps guide readable. */
export type GuidePanelHints = {
  /** Highlight the trace-strip pill for this component only. */
  traceStrip?: { focusComponent?: string };
  /** Highlight a Feature Store trace row by tool name and/or summary substring. */
  featureStore?: { focusTool?: string; focusTraceContains?: string };
  /** Expand + Look here on this Context Retriever tool row only. */
  contextRetriever?: { focusTool?: string };
  /** Look here on memory summary and/or one JSON field key. */
  agentMemory?: { focusSummary?: boolean; focusJsonKey?: string };
};

export const GUIDE_HIGHLIGHT_CLASS = "guide-panel-highlight";

export function textMatchesPatterns(text: string, patterns: string[] | undefined): boolean {
  if (!patterns?.length) return false;
  const lower = text.toLowerCase();
  return patterns.some((p) => lower.includes(p.toLowerCase()));
}

export function keyMatchesPatterns(key: string, patterns: string[] | undefined): boolean {
  if (!patterns?.length) return false;
  const lower = key.toLowerCase();
  return patterns.some((p) => lower.includes(p.toLowerCase()));
}

export function getPanelHints(step: GuideStep | null | undefined): GuidePanelHints | null {
  return step?.panelHints ?? null;
}
