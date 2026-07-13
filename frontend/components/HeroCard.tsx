"use client";
import type { HeroProfile, Verdict } from "@/lib/types";

interface Props {
  hero: HeroProfile;
  active: boolean;
  loading: boolean;
  // Verdict only renders after Run is clicked — before that, the card is
  // intentionally neutral so the audience commits to a guess first.
  verdict: Verdict | null;
  onSelect: () => void;
  // Wave 7n: Shift+click on Run forces a cache bypass (fresh agent run that
  // still writes-through to cache). Presenters know; no audience-facing hint.
  onRun: (bypassCache: boolean) => void;
  /** When guide mode owns the run step, hide the card Run button. */
  guideHideRun?: boolean;
}

const verdictMeta: Record<Verdict, { label: string; cls: string }> = {
  approve: { label: "Approve", cls: "bg-verdict-approve/15 text-verdict-approve border-verdict-approve/40" },
  review: { label: "Review Required", cls: "bg-verdict-review/15 text-verdict-review border-verdict-review/40" },
  block: { label: "Block", cls: "bg-verdict-block/15 text-verdict-block border-verdict-block/40" },
};

export function HeroCard({ hero, active, loading, verdict, onSelect, onRun, guideHideRun }: Props) {
  return (
    <button
      type="button"
      onClick={onSelect}
      data-testid={`hero-card-${hero.key}`}
      data-guide={`hero-${hero.key}`}
      data-active={active}
      data-verdict-revealed={verdict ? "true" : "false"}
      className={`group relative flex flex-col gap-3 rounded-redis border bg-redis-bg-secondary p-6 text-left transition-colors duration-200 ${
        active ? "border-redis-hyper" : "border-redis-border hover:border-redis-border-secondary"
      }`}
    >
      {active && (
        <span className="absolute -top-px left-0 h-[3px] w-full rounded-t-redis bg-redis-hyper" />
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-redis-body text-xl font-semibold">{hero.name}</div>
          <div className="font-redis-mono text-xs uppercase tracking-wider text-redis-text-muted">
            {hero.homeCity}, {hero.homeCountry} · ····{hero.cardLast4}
          </div>
        </div>
        {verdict && (
          <span
            data-testid={`hero-verdict-${hero.key}`}
            data-verdict={verdict}
            className={`verdict-reveal rounded-redis border px-2.5 py-1 font-redis-mono text-[11px] uppercase tracking-wider ${verdictMeta[verdict].cls}`}
          >
            {verdictMeta[verdict].label}
          </span>
        )}
      </div>

      <p
        data-testid={`hero-bio-${hero.key}`}
        className="flex-1 font-redis-body text-sm leading-relaxed text-redis-text-secondary"
      >
        {hero.bio}
      </p>

      <div className="mt-1 border-t border-redis-border pt-3">
        <div className="font-redis-mono text-[10px] uppercase tracking-wider text-redis-text-muted">
          📍 Scenario
        </div>
        <p
          data-testid={`hero-scenario-${hero.key}`}
          className="mt-1.5 font-redis-body text-sm leading-snug text-redis-text"
        >
          {hero.scenario}
        </p>
        <p
          data-testid={`hero-prompt-${hero.key}`}
          className="mt-2 font-redis-body text-[12px] italic text-redis-text-muted"
        >
          What's your call? Approve · Review Required · Block
        </p>
      </div>

      {guideHideRun ? (
        <p
          data-testid={`hero-run-hidden-${hero.key}`}
          className="mt-auto rounded-redis border border-dashed border-redis-border px-4 py-2.5 text-center font-redis-body text-xs text-redis-text-muted"
        >
          Use <span className="font-semibold text-redis-hyper">Run scenario</span> in the guide
          panel →
        </p>
      ) : (
        <span
          role="button"
          tabIndex={-1}
          onClick={(e) => {
            e.stopPropagation();
            onRun(e.shiftKey);
          }}
          data-testid={`run-${hero.key}`}
          data-guide={`hero-run-${hero.key}`}
          className={`mt-auto inline-flex min-h-11 cursor-pointer items-center justify-center rounded-redis border border-redis-border-secondary border-l-[4px] border-l-redis-hyper bg-redis-bg-tertiary px-6 py-2 font-redis-body text-sm font-semibold text-redis-text transition-colors duration-200 hover:bg-redis-border ${
            loading ? "opacity-70" : ""
          }`}
        >
          {loading ? "Scoring…" : "▶ Run scenario"}
        </span>
      )}
    </button>
  );
}
