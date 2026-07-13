"use client";

import { useEffect, useRef, useState } from "react";
import { useDemoGuide } from "./DemoGuideProvider";
import type { GuideStep } from "@/lib/demoGuide";
import {
  measureGuideTargetRect,
  resolveScrollAnchor,
  scrollBlockForStep,
  scrollGuideTargetIntoView,
} from "@/lib/guideScroll";

type Rect = { top: number; left: number; width: number; height: number };

function resolveTarget(step: GuideStep): Element | null {
  const primary = document.querySelector(step.target);
  if (primary) return primary;
  if (step.target === '[data-guide="langcache-verdict"]') {
    return document.querySelector('[data-guide="langcache-verdict"]')
      ?? document.querySelector('[data-guide="verdict-card"]');
  }
  return null;
}

function toRect(r: DOMRect): Rect {
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

export function GuideSpotlight() {
  const { guideMode, currentStep, currentStepIndex } = useDemoGuide();
  const [rect, setRect] = useState<Rect | null>(null);
  const [scrolling, setScrolling] = useState(false);
  const stepKeyRef = useRef<string>("");
  const scrollingRef = useRef(false);

  useEffect(() => {
    if (!guideMode || !currentStep) {
      setRect(null);
      setScrolling(false);
      scrollingRef.current = false;
      stepKeyRef.current = "";
      return;
    }

    const stepKey = `${currentStepIndex}:${currentStep.id}`;
    const stepChanged = stepKeyRef.current !== stepKey;
    stepKeyRef.current = stepKey;

    let cancelled = false;

    async function alignAndMeasure(scrollFirst: boolean) {
      const el = resolveTarget(currentStep!);
      if (!el || cancelled) {
        setRect(null);
        setScrolling(false);
        scrollingRef.current = false;
        return;
      }

      if (scrollFirst) {
        scrollingRef.current = true;
        setScrolling(true);
        setRect(null);
        const scrollEl = resolveScrollAnchor(currentStep!) ?? el;
        await scrollGuideTargetIntoView(scrollEl, scrollBlockForStep(currentStep!), true);
        if (cancelled) return;
        scrollingRef.current = false;
        setScrolling(false);
      }

      setRect(toRect(measureGuideTargetRect(el, true)));
    }

    void alignAndMeasure(stepChanged);

    function updateRectOnly() {
      if (cancelled || scrollingRef.current) return;
      const el = resolveTarget(currentStep!);
      if (!el) {
        setRect(null);
        return;
      }
      setRect(toRect(measureGuideTargetRect(el, true)));
    }

    const el = resolveTarget(currentStep);
    const ro = new ResizeObserver(updateRectOnly);
    if (el) ro.observe(el);
    window.addEventListener("scroll", updateRectOnly, true);
    window.addEventListener("resize", updateRectOnly);
    const id = window.setInterval(updateRectOnly, 300);

    return () => {
      cancelled = true;
      ro.disconnect();
      window.removeEventListener("scroll", updateRectOnly, true);
      window.removeEventListener("resize", updateRectOnly);
      window.clearInterval(id);
    };
  }, [guideMode, currentStep, currentStepIndex]);

  if (!guideMode || !rect || scrolling) return null;

  const pad = 8;
  const t = rect.top - pad;
  const l = rect.left - pad;
  const w = rect.width + pad * 2;
  const h = rect.height + pad * 2;

  return (
    <div
      data-testid="guide-spotlight"
      className="pointer-events-none fixed inset-0 z-[35]"
      aria-hidden
    >
      <svg className="absolute inset-0 h-full w-full">
        <defs>
          <mask id="guide-spot-mask">
            <rect x="0" y="0" width="100%" height="100%" fill="white" />
            <rect x={l} y={t} width={w} height={h} rx="8" fill="black" />
          </mask>
        </defs>
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          fill="rgba(10, 26, 35, 0.72)"
          mask="url(#guide-spot-mask)"
        />
      </svg>
      <div
        className="guide-spotlight-ring absolute rounded-redis border-2 border-redis-hyper"
        style={{ top: t, left: l, width: w, height: h }}
      />
    </div>
  );
}
