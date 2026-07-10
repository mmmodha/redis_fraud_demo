import type { GuideStep } from "@/lib/demoGuide";

/** Fixed TopBar + breathing room when scrolling guide targets into view. */
export const GUIDE_SCROLL_TOP_OFFSET = 88;

type ScrollBlock = "start" | "center";

const HERO_RUN_TARGET = /hero-run-(mike|jane|alex|sarah)/;

/** Element to scroll into view — hero card top for run steps, not the Run button. */
export function resolveScrollAnchor(step: GuideStep): Element | null {
  const runMatch = step.target.match(HERO_RUN_TARGET);
  if (runMatch) {
    const heroKey = runMatch[1];
    return (
      document.querySelector(`[data-guide="hero-${heroKey}"]`) ??
      document.querySelector('[data-guide="hero-grid"]')
    );
  }
  if (step.target === '[data-guide="langcache-verdict"]') {
    return (
      document.querySelector('[data-guide="langcache-verdict"]') ??
      document.querySelector('[data-guide="verdict-card"]')
    );
  }
  return document.querySelector(step.target);
}

export function scrollBlockForStep(step: GuideStep): ScrollBlock {
  const t = step.target;
  if (
    t.includes("hero-grid") ||
    t.includes("hero-mike") ||
    t.includes("hero-jane") ||
    t.includes("hero-alex") ||
    t.includes("hero-sarah") ||
    t.includes("hero-run-")
  ) {
    return "start";
  }
  return "center";
}

function waitForScrollSettle(ms = 520): Promise<void> {
  return new Promise((resolve) => {
    let settled = false;
    const done = () => {
      if (settled) return;
      settled = true;
      resolve();
    };
    if (typeof window !== "undefined" && "onscrollend" in window) {
      window.addEventListener("scrollend", done, { once: true });
    }
    window.setTimeout(done, ms);
  });
}

/** Scroll so the target sits in a sensible viewport band (accounts for fixed TopBar). */
export async function scrollGuideTargetIntoView(
  el: Element,
  block: ScrollBlock,
): Promise<void> {
  const rect = el.getBoundingClientRect();
  const docTop = window.scrollY + rect.top;
  const viewportH = window.innerHeight;
  const maxScroll = Math.max(0, document.documentElement.scrollHeight - viewportH);

  let targetScroll: number;
  if (block === "start") {
    targetScroll = docTop - GUIDE_SCROLL_TOP_OFFSET;
  } else {
    const visibleH = viewportH - GUIDE_SCROLL_TOP_OFFSET - 32;
    targetScroll = docTop - GUIDE_SCROLL_TOP_OFFSET - (visibleH - rect.height) / 2;
  }

  targetScroll = Math.max(0, Math.min(targetScroll, maxScroll));

  if (Math.abs(window.scrollY - targetScroll) < 4) {
    return;
  }

  window.scrollTo({ top: targetScroll, behavior: "smooth" });
  await waitForScrollSettle();
  // One frame so layout settles after scroll.
  await new Promise<void>((r) => requestAnimationFrame(() => r()));
}

export function measureGuideTargetRect(el: Element): DOMRect {
  return el.getBoundingClientRect();
}
