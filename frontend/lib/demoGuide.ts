import type { GuidePanelHints } from "./guidePanelHints";
import type { IrisDiagramSlug } from "./irisDiagrams";

export type HeroKey = "mike" | "jane" | "alex" | "sarah";

/** Shared presenter mantra — LLM-agnostic. */
export const GUIDE_MANTRA = "Same LLM. Same policy docs. Different context.";

export type GuideEvent =
  | { type: "hero-select"; hero: HeroKey }
  | { type: "hero-run"; hero: HeroKey }
  | { type: "hero-cache-hit"; hero: HeroKey }
  | { type: "score-complete"; hero: HeroKey }
  | { type: "trace-component"; hero: HeroKey; component: string }
  | { type: "otp-confirmed"; hero: HeroKey }
  | { type: "scroll-chatbot" }
  | { type: "chat-prompt"; index: number }
  | { type: "chat-sent" }
  | { type: "chat-cache-hit" }
  | { type: "guide-bootstrap"; hero: HeroKey };

export type GuideAdvance =
  | { mode: "manual"; requiresScore?: boolean; requiresOtp?: boolean; requiresCacheHit?: boolean }
  | { mode: "event"; event: GuideEvent };

export type GuideStep = {
  id: string;
  title: string;
  instruction: string;
  presenterLine?: string;
  redisBenefit?: string;
  target: string;
  advance: GuideAdvance;
  hero?: HeroKey;
  suggestedAction?: "run-hero" | "type-message" | "select-hero" | "close-guide";
  suggestedText?: string;
  summaryItems?: string[];
  activateHero?: HeroKey;
  /** Auto-expand and highlight IRIS panel subsections for this step. */
  panelHints?: GuidePanelHints;
  /** Animated IRIS architecture diagram (same assets as "How IRIS works"). */
  irisDiagram?: IrisDiagramSlug;
};

export const GUIDE_STEPS: GuideStep[] = [
  // ── Intro ──────────────────────────────────────────────────────────────
  {
    id: "welcome",
    title: "Welcome to the Fraud Command Center",
    instruction:
      "This demo shows how Redis helps banks make faster, more accurate fraud decisions — and helps any LLM give better analyst answers. We'll walk four customer stories at your pace.",
    presenterLine: GUIDE_MANTRA,
    target: '[data-guide="hero-grid"]',
    advance: { mode: "manual" },
  },
  {
    id: "meet-mike",
    title: "Meet Mike — everyday spending",
    instruction:
      "Mike buys a $6.75 coffee in Austin. Read the scenario on his card — what would you call it: approve, verify with OTP, or block?",
    presenterLine: "What do you think? Approve, verify with OTP, or block?",
    target: '[data-guide="hero-mike"]',
    hero: "mike",
    activateHero: "mike",
    advance: { mode: "manual" },
  },

  // ── Mike — full tutorial ───────────────────────────────────────────────
  {
    id: "mike-run",
    title: "Run Mike's scenario",
    instruction:
      'Click **Run scenario** in this panel. Watch the verdict appear — then we\'ll walk through why Redis decided that way.',
    hero: "mike",
    target: '[data-guide="hero-mike"]',
    suggestedAction: "run-hero",
    advance: { mode: "event", event: { type: "hero-run", hero: "mike" } },
  },
  {
    id: "mike-verdict",
    title: "The verdict — fast and confident",
    instruction:
      "APPROVE with high confidence. Redis had enough data to decide quickly — before the full AI explanation finished. Note the confidence bar and response time.",
    presenterLine: "Decision first — then the why.",
    redisBenefit:
      "For routine transactions, Redis delivers an accurate answer in milliseconds. Most approvals never need a human.",
    target: '[data-guide="verdict-card"]',
    hero: "mike",
    advance: { mode: "manual" },
  },
  {
    id: "mike-trace",
    title: "What happened behind the scenes",
    instruction:
      "Each step here is data Redis fetched for the agent — features, customer records, memory. That context is assembled in milliseconds so any LLM can reason on facts, not guesses.",
    redisBenefit:
      "Redis gathers the right data points in parallel. The LLM receives a complete picture instead of searching from scratch.",
    target: '[data-guide="trace-strip"]',
    hero: "mike",
    irisDiagram: "context-retriever",
    panelHints: {
      traceStrip: { focusComponent: "feature_store" },
    },
    advance: { mode: "manual" },
  },
  {
    id: "mike-analyst",
    title: "Analyst summary — AI with real data",
    instruction:
      "The written explanation uses the same Redis data you just saw. Wait for it to load, then continue. This is what an analyst reads — grounded in facts, not generic policy boilerplate.",
    presenterLine: GUIDE_MANTRA,
    redisBenefit:
      "Any LLM writes a better summary when Redis supplies live customer data. Accuracy goes up; hallucinations go down.",
    target: '[data-guide="analyst-summary"]',
    hero: "mike",
    advance: { mode: "manual", requiresScore: true },
  },
  {
    id: "mike-feature-store",
    title: "Feature Store — the accuracy scorecard",
    instruction:
      "Feature Store holds ready-to-use data points about this card: typical spend, location, velocity, merchant type. For Mike, everything looks normal — coffee, home city, low amount.",
    presenterLine: "The boring path. Most decisions never touch a human.",
    redisBenefit:
      "Feature Store gives the bank pre-computed signals for faster, more accurate decisions — no manual lookup, no waiting on an LLM.",
    target: '[data-guide="panel-feature-store"]',
    hero: "mike",
    panelHints: {
      featureStore: { focusTraceContains: "within baseline" },
    },
    advance: { mode: "manual" },
  },
  {
    id: "mike-context-retriever",
    title: "Context Retriever — live customer lookup",
    instruction:
      "When the agent needs more detail, Context Retriever pulls live customer data from Redis — devices, transactions, profile fields — in milliseconds.",
    redisBenefit:
      "Context Retriever connects the LLM to up-to-the-second customer data. Decisions stay accurate even as circumstances change.",
    target: '[data-guide="panel-context-retriever"]',
    hero: "mike",
    irisDiagram: "context-retriever",
    advance: { mode: "manual" },
  },
  {
    id: "mike-bridge",
    title: "Most transactions look like Mike",
    instruction:
      "Routine spend, fast decision, clear explanation. Next up: a charge that'll split the room — make your call before you run it.",
    target: '[data-guide="hero-jane"]',
    advance: { mode: "manual" },
  },

  // ── Jane — focused ─────────────────────────────────────────────────────
  {
    id: "jane-meet",
    title: "Jane — the $1,820 question",
    instruction:
      "Luxury boutique in Singapore — foreign country, high amount. Read Jane's scenario on her card — what would you call it: approve, verify with OTP, or block?",
    presenterLine: "What do you think? Approve, verify with OTP, or block?",
    hero: "jane",
    target: '[data-guide="hero-jane"]',
    activateHero: "jane",
    advance: { mode: "manual" },
  },
  {
    id: "jane-run",
    title: "Run Jane's scenario",
    instruction:
      'Click **Run scenario** in this panel. Watch whether Redis approves despite the risky-looking signals.',
    hero: "jane",
    target: '[data-guide="hero-jane"]',
    suggestedAction: "run-hero",
    advance: { mode: "event", event: { type: "hero-run", hero: "jane" } },
  },
  {
    id: "jane-verdict",
    title: "APPROVE — context changed everything",
    instruction:
      "APPROVE despite risky-looking signals. The raw features screamed fraud — but Redis had extra context that changed the outcome.",
    presenterLine: GUIDE_MANTRA,
    redisBenefit:
      "Blocking a good customer mid-purchase costs loyalty. Redis context prevents expensive false alarms.",
    target: '[data-guide="verdict-card"]',
    hero: "jane",
    advance: { mode: "manual" },
  },
  {
    id: "jane-panels",
    title: "Travel memory saved the sale",
    instruction:
      "The highlighted line is the key: Jane is travelling to Singapore this week. That one memory note explains why APPROVE makes sense despite foreign + luxury signals.",
    presenterLine: "The data the scorecard alone couldn't see.",
    redisBenefit:
      "Agent Memory stores travel plans and analyst notes — the missing piece that turns a false block into an approve.",
    target: '[data-guide="panel-agent-memory"]',
    hero: "jane",
    irisDiagram: "agent-memory",
    panelHints: {
      agentMemory: { focusSummary: true },
    },
    advance: { mode: "manual" },
  },

  // ── Jane chatbot ─────────────────────────────────────────────────────────
  {
    id: "chatbot-intro",
    title: "Jane's analyst chatbot",
    instruction:
      "Scroll down to the Insight Chatbot section below. When you can see it, read this panel and click Continue — we'll try a sample question next.",
    presenterLine: GUIDE_MANTRA,
    hero: "jane",
    target: '[data-guide="chatbot"]',
    advance: { mode: "manual" },
  },
  {
    id: "chat-prompt-0",
    title: 'Try: "Any upcoming travel?"',
    instruction:
      'Click the first suggested question. Watch both pipelines respond — same LLM, but only one side has live customer context from Redis.',
    target: '[data-guide="chat-prompt-0"]',
    advance: { mode: "event", event: { type: "chat-prompt", index: 0 } },
  },
  {
    id: "chat-compare",
    title: "Same LLM, different answer quality",
    instruction:
      "Compare both sides. One answer cites Jane's real travel plans; the other gives generic policy text. Redis is the difference.",
    presenterLine: GUIDE_MANTRA,
    redisBenefit:
      "Redis gives any LLM the customer-specific facts it needs. Better answers, fewer wrong conclusions, less analyst rework.",
    target: '[data-guide="chatbot"]',
    irisDiagram: "context-retriever",
    advance: { mode: "manual" },
  },
  {
    id: "chat-langcache-type",
    title: "LangCache — skip repeat work",
    instruction:
      'Copy the question below into the chat box (or use **Insert into chat**), then press Enter or click "Ask both" to send. LangCache recognises paraphrases — the LLM does not need to run again.',
    suggestedAction: "type-message",
    suggestedText: "Do they have travel planned?",
    target: '[data-guide="chat-send"]',
    irisDiagram: "langcache",
    advance: { mode: "event", event: { type: "chat-cache-hit" } },
  },
  {
    id: "chat-langcache-savings",
    title: "Token savings on every cache hit",
    instruction:
      "Green banner and savings counter show cost avoided. Repeat analyst questions are answered from cache — fast and free.",
    presenterLine: "Same answer quality, fraction of the cost.",
    redisBenefit:
      "LangCache cuts LLM spend on repeat and similar questions. Works with any model provider.",
    target: '[data-guide="langcache-savings"]',
    irisDiagram: "langcache",
    advance: { mode: "manual" },
  },
  {
    id: "jane-rerun",
    title: "LangCache on fraud scoring too",
    instruction:
      'Click **Run scenario** in this panel to re-run Jane. Same inputs — watch whether the second run feels different on the verdict card.',
    presenterLine: "Same question, second time — what changed?",
    hero: "jane",
    target: '[data-guide="hero-jane"]',
    suggestedAction: "run-hero",
    advance: { mode: "event", event: { type: "hero-cache-hit", hero: "jane" } },
  },
  {
    id: "jane-rerun-show",
    title: "LangCache captured the approval",
    instruction:
      "See the green strip on the verdict card: tokens skipped and milliseconds served from cache. The full agent trace replayed without calling the LLM again.",
    presenterLine: "Same APPROVE — fraction of the cost and time.",
    redisBenefit:
      "LangCache stores fraud verdicts so repeat scoring skips expensive LLM calls — sub-10ms replay vs a full agent run.",
    hero: "jane",
    target: '[data-guide="langcache-verdict"]',
    irisDiagram: "langcache",
    advance: { mode: "manual", requiresCacheHit: true },
  },
  {
    id: "jane-complete-bridge",
    title: "Jane's story is complete",
    instruction:
      "You saw context change the fraud call, analyst chat with live data, and LangCache on replay. Next: two more customers — run each scenario before reading ahead in the guide.",
    target: '[data-guide="hero-alex"]',
    advance: { mode: "manual" },
  },

  // ── Alex — focused ─────────────────────────────────────────────────────
  {
    id: "alex-meet",
    title: "Alex — wrong device, wrong continent",
    instruction:
      "Electronics in São Paulo — read Alex's bio and scenario on his card. What would you call it: approve, verify with OTP, or block?",
    presenterLine: "What do you think? Approve, verify with OTP, or block?",
    hero: "alex",
    target: '[data-guide="hero-alex"]',
    activateHero: "alex",
    advance: { mode: "manual" },
  },
  {
    id: "alex-run",
    title: "Run Alex's scenario",
    instruction:
      'Click **Run scenario** in this panel and see what Redis decides.',
    hero: "alex",
    target: '[data-guide="hero-alex"]',
    suggestedAction: "run-hero",
    advance: { mode: "event", event: { type: "hero-run", hero: "alex" } },
  },
  {
    id: "alex-verdict",
    title: "BLOCK — fraud stopped in time",
    instruction:
      "BLOCK with high confidence. Unusual spend, new device, wrong country — Feature Store and Context Retriever both flagged risk.",
    redisBenefit:
      "Accurate data points let the bank stop fraud in seconds — before money leaves the account.",
    target: '[data-guide="verdict-card"]',
    hero: "alex",
    advance: { mode: "manual" },
  },
  {
    id: "alex-panels",
    title: "Data points that exposed the fraud",
    instruction:
      "Two signals drove BLOCK: impossible travel in Feature Store, and a device Alex has never used. Each highlighted row is one reason the bank stopped the swipe.",
    redisBenefit:
      "Redis combines real-time features and live lookups — one source of truth for accurate fraud detection.",
    target: '[data-testid="iris-rail"]',
    hero: "alex",
    irisDiagram: "context-retriever",
    panelHints: {
      featureStore: { focusTraceContains: "impossible-travel" },
      contextRetriever: { focusTool: "get_devices_for_customer" },
    },
    advance: { mode: "manual" },
  },

  // ── Sarah — focused ────────────────────────────────────────────────────
  {
    id: "sarah-meet",
    title: "Sarah — the split decision",
    instruction:
      "Tiffany & Co in Manhattan for $1,450 — friendly profile, high value, away from home. Read Sarah's scenario — what would you call it: approve, verify with OTP, or block?",
    presenterLine: "What do you think? Approve, verify with OTP, or block?",
    hero: "sarah",
    target: '[data-guide="hero-sarah"]',
    activateHero: "sarah",
    advance: { mode: "manual" },
  },
  {
    id: "sarah-run",
    title: "Run Sarah's scenario",
    instruction:
      'Click **Run scenario** in this panel. Watch for Review Required and the OTP confirmation flow.',
    hero: "sarah",
    target: '[data-guide="hero-sarah"]',
    suggestedAction: "run-hero",
    advance: { mode: "event", event: { type: "hero-run", hero: "sarah" } },
  },
  {
    id: "sarah-breadcrumb",
    title: "Verify identity (OTP) — confirm without blocking",
    instruction:
      "REVIEW first, then OTP confirmed, then APPROVED. The bank texts a one-time code to confirm it's really Sarah before approving the purchase. Wait for the OTP step before continuing. This protects the customer without killing the sale.",
    presenterLine:
      "Confirm it's really Sarah — don't block her at the register.",
    redisBenefit:
      "Redis gives enough context to verify identity instead of blocking: trusted device, travel noted, but spend is unusually high.",
    target: '[data-guide="verdict-card"]',
    hero: "sarah",
    advance: { mode: "manual", requiresOtp: true },
  },
  {
    id: "sarah-panels",
    title: "Why OTP verification was the right call",
    instruction:
      "Sarah is travelling (memory note) but the spend is ~5× her norm (Feature Store). That combination is why Redis chose verify identity instead of block or auto-approve.",
    redisBenefit:
      "Rich data points help the bank avoid both fraud losses and unnecessary blocks — the customer keeps shopping.",
    target: '[data-testid="iris-rail"]',
    hero: "sarah",
    irisDiagram: "agent-memory",
    panelHints: {
      agentMemory: { focusSummary: true },
      featureStore: { focusTraceContains: "5x typical" },
    },
    advance: { mode: "manual" },
  },

  // ── Summary & finish ───────────────────────────────────────────────────
  {
    id: "guide-summary",
    title: "What Redis delivered",
    instruction:
      "You saw how Redis improves fraud accuracy, analyst productivity, and LLM cost — regardless of which AI model the bank uses.",
    presenterLine: GUIDE_MANTRA,
    redisBenefit:
      "Context Retriever pulls live customer facts so the bank blocks real fraud without freezing genuine spend. LangCache reuses prior LLM answers and verdicts — cutting token spend at scale while keeping responses fast for every analyst and channel.",
    target: '[data-guide="hero-grid"]',
    summaryItems: [
      "Feature Store — ready-made data points (spend, location, velocity) for accurate decisions",
      "Context Retriever — stop fraud in seconds without blocking good customers mid-purchase",
      "Agent Memory — relationship context (travel, notes) that raw scores miss",
      "Fast verdicts — routine decisions in milliseconds, no analyst queue",
      "Analyst summaries — AI explanations grounded in Redis data, not generic text",
      "LangCache — slash repeat LLM cost org-wide; cached answers in milliseconds",
      "Context Surface chat — same LLM as basic RAG, but with customer data attached",
    ],
    suggestedAction: "close-guide",
    advance: { mode: "manual" },
  },
];

export function eventsMatch(step: GuideStep, event: GuideEvent): boolean {
  if (step.advance.mode !== "event") return false;
  const a = step.advance.event;
  if (a.type !== event.type) return false;
  switch (a.type) {
    case "hero-select":
    case "hero-run":
    case "hero-cache-hit":
    case "score-complete":
    case "otp-confirmed":
    case "guide-bootstrap":
      return "hero" in event && "hero" in a && event.hero === a.hero;
    case "trace-component":
      return (
        event.type === "trace-component" &&
        a.type === "trace-component" &&
        event.component === a.component &&
        event.hero === a.hero
      );
    case "chat-prompt":
      return event.type === "chat-prompt" && event.index === a.index;
    default:
      return true;
  }
}

export function stepExpectsEvent(step: GuideStep | null, eventType: GuideEvent["type"]): boolean {
  if (!step || step.advance.mode !== "event") return false;
  return step.advance.event.type === eventType;
}

export function isGuideRunStepForHero(
  step: GuideStep | null,
  heroKey: HeroKey,
): boolean {
  return step?.suggestedAction === "run-hero" && step.hero === heroKey;
}

/** Card Run is guide-panel only on the designated run step for that hero. */
export function guideAllowsHeroRun(
  step: GuideStep | null,
  heroKey: HeroKey,
): boolean {
  return isGuideRunStepForHero(step, heroKey);
}

export function guideAllowsChatPrompt(
  step: GuideStep | null,
  index: number,
): boolean {
  if (!step || step.advance.mode !== "event") return false;
  const ev = step.advance.event;
  return ev.type === "chat-prompt" && ev.index === index;
}

/** Freeform chat input + Ask both — only on the LangCache typing step. */
export function guideAllowsChatFreeSend(step: GuideStep | null): boolean {
  return step?.suggestedAction === "type-message";
}

export function isGuideHeroRunEventStep(step: GuideStep | null): boolean {
  return (
    step?.suggestedAction === "run-hero" &&
    step.advance.mode === "event" &&
    step.advance.event.type === "hero-run"
  );
}

export function isGuideCacheReplayStep(step: GuideStep | null): boolean {
  return (
    step?.advance.mode === "event" &&
    step.advance.event.type === "hero-cache-hit"
  );
}
