"use client";

import { useDemoGuideOptional } from "@/components/DemoGuideProvider";
import { getPanelHints } from "@/lib/guidePanelHints";

export function useGuidePanelHints() {
  const guide = useDemoGuideOptional();
  const step = guide?.currentStep ?? null;
  return {
    guideMode: guide?.guideMode ?? false,
    stepId: step?.id ?? null,
    hints: guide?.guideMode ? getPanelHints(step) : null,
  };
}
