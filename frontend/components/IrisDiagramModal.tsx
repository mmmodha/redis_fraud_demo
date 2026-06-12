"use client";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import lottie, { type AnimationItem } from "lottie-web";

type PanelSlug = "rdi" | "context-retriever" | "agent-memory" | "langcache";

type Panel = {
  slug: PanelSlug;
  title: string;
  subtitle: string;
};

const PANELS: Panel[] = [
  {
    slug: "rdi",
    title: "Redis Data Integration",
    subtitle: "Streams Postgres / Kafka changes into Redis in real time",
  },
  {
    slug: "context-retriever",
    title: "Context Retriever",
    subtitle: "Pulls fresh customer + transaction context for every decision",
  },
  {
    slug: "agent-memory",
    title: "Agent Memory",
    subtitle: "Persists short-term + long-term agent state across turns",
  },
  {
    slug: "langcache",
    title: "LangCache",
    subtitle: "Semantic cache for repeated LLM prompts to cut latency and cost",
  },
];

export function IrisDiagramModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const containerRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const animationsRef = useRef<AnimationItem[]>([]);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const backButtonRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const [focused, setFocused] = useState<PanelSlug | null>(null);
  // Mirror `focused` in a ref so the keydown listener reads the latest value
  // without forcing a re-subscribe (which would reset previouslyFocused).
  const focusedRef = useRef<PanelSlug | null>(null);
  useEffect(() => {
    focusedRef.current = focused;
  }, [focused]);

  // Always start in overview when the modal opens, and clear focused state on
  // close so the next open is a clean slate.
  useEffect(() => {
    if (!open) setFocused(null);
  }, [open]);

  // Mount / unmount Lottie animations alongside the modal open state. The same
  // container DOM nodes are reused across overview / focused layouts (only CSS
  // changes), so AnimationItem instances persist while zooming in and out.
  useEffect(() => {
    if (!open) return;
    const items: AnimationItem[] = [];
    for (const panel of PANELS) {
      const container = containerRefs.current[panel.slug];
      if (!container) continue;
      const item = lottie.loadAnimation({
        container,
        renderer: "svg",
        loop: true,
        autoplay: true,
        path: `/iris/${panel.slug}.json`,
      });
      items.push(item);
    }
    animationsRef.current = items;
    return () => {
      for (const item of items) item.destroy();
      animationsRef.current = [];
    };
  }, [open]);

  // ESC + focus trap. ESC returns to overview first when a panel is focused,
  // then closes the modal on a second press. Backdrop click still closes from
  // any state (handled in the JSX). Saves / restores the previously focused
  // element on open / close.
  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        if (focusedRef.current) {
          setFocused(null);
        } else {
          onClose();
        }
      } else if (e.key === "Tab") {
        // Simple focus trap: keep focus within the dialog.
        const root = dialogRef.current;
        if (!root) return;
        const focusables = root.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      previouslyFocused.current?.focus?.();
    };
  }, [open, onClose]);

  // Move keyboard focus to the most appropriate control whenever the modal
  // opens or the focused-panel state changes.
  useEffect(() => {
    if (!open) return;
    if (focused) {
      backButtonRef.current?.focus();
    } else {
      closeButtonRef.current?.focus();
    }
  }, [open, focused]);

  // Track client mount so the portal target (document.body) exists before
  // rendering. Avoids SSR / hydration mismatch.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!open || !mounted) return null;

  // Render via portal so ancestors with backdrop-filter / transform / filter
  // (e.g. the sticky TopBar with backdrop-blur) cannot trap our fixed-position
  // overlay inside their containing block.
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/70 p-4 backdrop-blur sm:p-8"
      onClick={onClose}
      data-testid="iris-diagram-modal"
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="iris-diagram-modal-title"
        className="relative flex max-h-[90vh] w-full max-w-6xl flex-col rounded-redis border border-redis-border bg-redis-bg shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-shrink-0 items-start justify-between border-b border-redis-border px-6 py-4">
          <div>
            <h2
              id="iris-diagram-modal-title"
              className="font-redis-body text-xl font-semibold text-redis-text"
            >
              How Redis IRIS works
            </h2>
            <p className="mt-1 font-redis-mono text-[11px] uppercase tracking-wider text-redis-text-muted">
              Four layers · live on every decision
            </p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close diagram"
            className="rounded-redis border border-redis-border bg-redis-bg-secondary px-2.5 py-1 font-redis-mono text-sm text-redis-text-secondary hover:border-redis-hyper hover:text-redis-text"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {focused && (
            <button
              ref={backButtonRef}
              type="button"
              onClick={() => setFocused(null)}
              className="mb-4 inline-flex items-center gap-1 rounded-redis border border-redis-border bg-redis-bg-secondary px-3 py-1 font-redis-mono text-xs text-redis-text-secondary hover:border-redis-hyper hover:text-redis-text"
            >
              ← Back to overview
            </button>
          )}

          <div className="grid grid-cols-12 gap-4">
            {PANELS.map((panel) => {
              const isFocusedPanel = focused === panel.slug;
              const isThumb = focused !== null && !isFocusedPanel;
              // Overview uses Tailwind responsive classes (1 col on small, 2x2
              // on lg+). Focused mode pins exact spans + order via inline style
              // so the focused panel always sits on row 1 and thumbnails wrap
              // beneath it as a 3-up row.
              const spanClass =
                focused === null ? "col-span-12 lg:col-span-6" : "";
              const style: React.CSSProperties =
                focused === null
                  ? {}
                  : isFocusedPanel
                    ? { gridColumn: "span 12 / span 12", order: 0 }
                    : { gridColumn: "span 4 / span 4", order: 1 };
              return (
                <div
                  key={panel.slug}
                  style={style}
                  className={`group ${spanClass} cursor-pointer rounded-redis border border-redis-border bg-redis-bg-secondary ${
                    isThumb ? "p-3" : "p-4"
                  } transition hover:border-redis-hyper hover:shadow-lg`}
                  onClick={() =>
                    setFocused(isFocusedPanel ? null : panel.slug)
                  }
                  role="button"
                  tabIndex={0}
                  aria-label={
                    isFocusedPanel
                      ? `Return to overview from ${panel.title}`
                      : `Focus ${panel.title}`
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setFocused(isFocusedPanel ? null : panel.slug);
                    }
                  }}
                >
                  <div
                    className={`font-redis-body font-semibold text-redis-text ${
                      isThumb ? "text-xs" : "text-sm"
                    }`}
                  >
                    {panel.title}
                  </div>
                  {!isThumb && (
                    <div className="mt-1 font-redis-body text-xs text-redis-text-secondary">
                      {panel.subtitle}
                    </div>
                  )}
                  <div
                    ref={(el) => {
                      containerRefs.current[panel.slug] = el;
                    }}
                    className={`${isThumb ? "mt-2" : "mt-3"} ${
                      isFocusedPanel ? "aspect-[16/9]" : "aspect-video"
                    } w-full overflow-hidden rounded-redis bg-redis-bg-tertiary`}
                    data-testid={`iris-diagram-${panel.slug}`}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
