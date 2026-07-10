"use client";

import { useEffect, useRef } from "react";
import lottie, { type AnimationItem } from "lottie-web";
import {
  irisDiagramBySlug,
  type IrisDiagramSlug,
} from "@/lib/irisDiagrams";

export function GuideIrisDiagram({ slug }: { slug: IrisDiagramSlug }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const panel = irisDiagramBySlug(slug);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let item: AnimationItem | null = null;
    item = lottie.loadAnimation({
      container,
      renderer: "svg",
      loop: true,
      autoplay: true,
      path: panel.lottiePath,
    });
    return () => {
      item?.destroy();
    };
  }, [panel.lottiePath]);

  return (
    <div
      data-testid={`guide-iris-diagram-${slug}`}
      className="mt-4 overflow-hidden rounded-redis border border-redis-border bg-redis-bg-tertiary"
    >
      <div className="border-b border-redis-border px-3 py-2">
        <div className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-hyper">
          How it works
        </div>
        <div className="font-redis-body text-xs font-semibold text-redis-text">
          {panel.title}
        </div>
        <div className="mt-0.5 font-redis-body text-[11px] leading-snug text-redis-text-secondary">
          {panel.subtitle}
        </div>
      </div>
      <div
        ref={containerRef}
        className="aspect-video w-full bg-redis-bg-secondary"
        aria-hidden
      />
    </div>
  );
}
