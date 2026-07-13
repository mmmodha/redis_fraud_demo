// Deterministic mock trace data — matches the frozen Wave 3a AgentTrace
// schema and the storyboard outputs for the three heroes. Used until the
// real /agent/score endpoint is live and as the offline fallback inside
// the page so the UI renders even when the backend is down.

import type { AgentTrace, ScoreResponse, Verdict } from "./types";

function step(s: Partial<import("./types").TraceStep>): import("./types").TraceStep {
  return {
    component: "context_retriever",
    tool: "get_customer_context",
    input: {},
    output_summary: "",
    output_data: null,
    latency_ms: 30,
    redis_keys_touched: [],
    ...s,
  };
}

const MIKE_TRACE: AgentTrace = {
  llm_model: "stub-deterministic",
  total_latency_ms: 92,
  steps: [
    step({ component: "context_retriever", tool: "get_customer_context", input: { customer_id: "cust_mike" }, output_summary: "Customer Mike Rivera, home Austin US, 1 active card.", latency_ms: 18, redis_keys_touched: ["customer:cust_mike", "card:card_mike_visa"] }),
    step({ component: "feature_store", tool: "get_velocity_features", input: { card_id: "card_mike_visa" }, output_summary: "1h count=2, 24h amount=$48.20 — within baseline.", output_data: { count_1h: 2, amount_24h: 48.2, baseline_p95: 220 }, latency_ms: 6, redis_keys_touched: ["card:card_mike_visa:features"] }),
    step({ component: "policy_rag", tool: "search_policy", input: { query: "low-risk approval" }, output_summary: "Top chunk: 'Card-present, domestic, low-MCC merchants under $50 auto-approve.'", latency_ms: 34, redis_keys_touched: ["policy:0042"] }),
    step({ component: "llm", tool: "compose_verdict", input: {}, output_summary: "Velocity normal, established merchant, low-risk MCC.", latency_ms: 34, redis_keys_touched: [] }),
  ],
};

const JANE_TRACE: AgentTrace = {
  llm_model: "stub-deterministic",
  total_latency_ms: 612,
  steps: [
    step({ component: "context_retriever", tool: "get_customer_context", input: { customer_id: "cust_jane" }, output_summary: "Customer Jane Doe, home San Francisco US, active card 7788.", latency_ms: 22, redis_keys_touched: ["customer:cust_jane"] }),
    step({ component: "context_retriever", tool: "get_recent_transactions", input: { customer_id: "cust_jane", limit: 5 }, output_summary: "Last 5 tx: SFO coffee, Uber SFO, hotel Singapore, taxi Singapore, brunch Singapore.", latency_ms: 41, redis_keys_touched: ["card:card_jane_visa:tx:recent"] }),
    step({ component: "agent_memory", tool: "get_customer_memory", input: { customer_id: "cust_jane" }, output_summary: "Memory: 'travelling 10–17 Nov to Singapore'.", output_data: { travel_window: { start: "2026-11-10", end: "2026-11-17", destination: "Singapore" } }, latency_ms: 12, redis_keys_touched: ["mem:cust_jane"] }),
    step({ component: "context_retriever", tool: "get_merchant_reputation", input: { merchant_id: "merch_jane_boutique_sg" }, output_summary: "Orchard Luxe Boutique — trusted, dispute rate 0.4%.", latency_ms: 28, redis_keys_touched: ["merchant:merch_jane_boutique_sg"] }),
    step({ component: "policy_rag", tool: "search_policy", input: { query: "cross-border travel exception" }, output_summary: "Top chunk: 'Approve foreign card-present tx when declared travel window matches merchant country.'", latency_ms: 36, redis_keys_touched: ["policy:0117"] }),
    step({ component: "llm", tool: "compose_verdict", input: {}, output_summary: "Foreign high-value flagged by velocity but memory shows declared Singapore travel; merchant reputation trusted.", latency_ms: 473, redis_keys_touched: [] }),
  ],
};

const ALEX_TRACE: AgentTrace = {
  llm_model: "stub-deterministic",
  total_latency_ms: 488,
  steps: [
    step({ component: "context_retriever", tool: "get_customer_context", input: { customer_id: "cust_alex" }, output_summary: "Customer Alex Chen, home Seattle US, active card 3344.", latency_ms: 20, redis_keys_touched: ["customer:cust_alex"] }),
    step({ component: "context_retriever", tool: "get_devices_for_customer", input: { customer_id: "cust_alex" }, output_summary: "Known: dev_alex_macbook (US). Incoming dev_alex_unknown_android (BR) — FIRST SEEN.", output_data: { new_device: true, device_id: "dev_alex_unknown_android", country: "BR" }, latency_ms: 31, redis_keys_touched: ["device:dev_alex_macbook", "device:dev_alex_unknown_android"] }),
    step({ component: "feature_store", tool: "get_new_device_flag", input: { customer_id: "cust_alex", device_id: "dev_alex_unknown_android" }, output_summary: "new_device_24h=True first_seen=never", output_data: { new_device_24h: true, device_known_to_card: false }, latency_ms: 5, redis_keys_touched: ["feat:card_alex_visa", "feat:_dev:card_alex_visa"] }),
    step({ component: "feature_store", tool: "get_geo_entropy", input: { customer_id: "cust_alex" }, output_summary: "geo_entropy=0.920 — impossible-travel pattern (Seattle → São Paulo in 4h).", output_data: { geo_entropy: 0.92, impossible_travel: true }, latency_ms: 7, redis_keys_touched: ["card:card_alex_visa:features"] }),
    step({ component: "context_retriever", tool: "find_similar_fraud", input: { merchant_id: "merch_alex_electronics_br" }, output_summary: "2 matches in known-fraud cluster (electronics BR high-value).", latency_ms: 53, redis_keys_touched: ["idx:fraud_cases"] }),
    step({ component: "policy_rag", tool: "search_policy", input: { query: "new-device high-value block" }, output_summary: "Top chunk: 'Block first-seen device transactions above $1,000 in mismatched country pending step-up auth.'", latency_ms: 38, redis_keys_touched: ["policy:0203"] }),
    step({ component: "llm", tool: "compose_verdict", input: {}, output_summary: "First-seen device + impossible-travel + known-fraud cluster match.", latency_ms: 339, redis_keys_touched: [] }),
  ],
};

const SARAH_TRACE: AgentTrace = {
  llm_model: "stub-deterministic",
  total_latency_ms: 540,
  steps: [
    step({ component: "context_retriever", tool: "get_customer_context", input: { customer_id: "cust_sarah" }, output_summary: "Customer Sarah Kim, home Seattle US, active card 9911.", latency_ms: 22, redis_keys_touched: ["customer:cust_sarah"] }),
    step({ component: "context_retriever", tool: "get_recent_transactions", input: { customer_id: "cust_sarah", days: 7 }, output_summary: "Delta flight 52h ago, Marriott NYC 26h ago, JFK Hudson News + Manhattan coffee earlier today.", latency_ms: 38, redis_keys_touched: ["card:card_sarah_visa:tx:recent"] }),
    step({ component: "context_retriever", tool: "get_devices_for_customer", input: { customer_id: "cust_sarah" }, output_summary: "1 device: dev_sarah_iphone (iOS, US) — known 18+ months, no new device today.", latency_ms: 18, redis_keys_touched: ["device:dev_sarah_iphone"] }),
    step({ component: "agent_memory", tool: "get_customer_memory", input: { customer_id: "cust_sarah" }, output_summary: "Travel window: New York 9–13 Jun 2026. Analyst note: step-up over block on travel days.", output_data: { travel_window: { start: "2026-06-09", end: "2026-06-13", destination: "New York" } }, latency_ms: 12, redis_keys_touched: ["mem:cust_sarah"] }),
    step({ component: "context_retriever", tool: "get_pending_review", input: { customer_id: "cust_sarah" }, output_summary: "Pending $1,450 Tiffany & Co Manhattan (MCC 5944) on known iPhone — travel-confirmed, device known.", latency_ms: 11, redis_keys_touched: ["pending_review:cust_sarah"] }),
    step({ component: "feature_store", tool: "get_velocity_features", input: { card_id: "card_sarah_visa" }, output_summary: "24h amount = $1,471, p95 ~ $280 — 5x typical; geo-entropy low.", output_data: { p95_90d: 280, amount_24h: 1471, value_ratio: 5.18 }, latency_ms: 7, redis_keys_touched: ["card:card_sarah_visa:features"] }),
    step({ component: "context_retriever", tool: "get_merchant_reputation", input: { merchant_id: "merch_sarah_tiffany_ny" }, output_summary: "Tiffany & Co Manhattan — high reputation, jewelry (MCC 5944) novel for this customer.", latency_ms: 25, redis_keys_touched: ["merchant:merch_sarah_tiffany_ny"] }),
    step({ component: "context_retriever", tool: "get_disputes", input: { customer_id: "cust_sarah", days: 180 }, output_summary: "0 disputes in last 180 days.", latency_ms: 14, redis_keys_touched: ["disputes:cust_sarah"] }),
    step({ component: "policy_rag", tool: "search_policy", input: { query: "step-up auth travel-confirmed high-value novel MCC" }, output_summary: "Top chunk: 'Travel-confirmed customers with novel-category high-value charges route to step-up rather than block.'", latency_ms: 36, redis_keys_touched: ["policy:0084"] }),
    step({ component: "llm", tool: "compose_verdict", input: {}, output_summary: "Travel + device confirmed; value 5x typical + novel jewelry MCC → step-up.", latency_ms: 357, redis_keys_touched: [] }),
  ],
};

const TRACES: Record<string, { verdict: Verdict; confidence: number; reason: string; trace: AgentTrace }> = {
  cust_mike: { verdict: "approve", confidence: 0.92, reason: "Velocity normal, established merchant, low-risk MCC.", trace: MIKE_TRACE },
  cust_jane: { verdict: "approve", confidence: 0.78, reason: "Foreign tx flagged by velocity but memory shows declared Singapore travel; merchant reputation trusted.", trace: JANE_TRACE },
  cust_alex: { verdict: "block", confidence: 0.94, reason: "First-seen device + impossible-travel pattern + match against known fraud cluster.", trace: ALEX_TRACE },
  cust_sarah: { verdict: "review", confidence: 0.86, reason: "Travel + device confirmed. Value ~5x typical spend on a novel jewelry MCC — routing to OTP step-up rather than block.", trace: SARAH_TRACE },
};

export function mockScore(customerId: string): ScoreResponse {
  const m = TRACES[customerId];
  if (!m) {
    return {
      verdict: "review",
      confidence: 0.5,
      reason: "Insufficient context; routing for manual review.",
      trace: { llm_model: "stub-deterministic", total_latency_ms: 40, steps: [step({ output_summary: "Minimal context lookup.", latency_ms: 40 })] },
    };
  }
  return m;
}

// Wave 7j offline fallback: replays a mockScore trace as a stream of events
// so the trace strip + IRIS panels still light up progressively when the
// backend isn't reachable (e.g. running `next dev` without Docker up).
import type { ScoreStreamHandlers } from "./api";

export async function mockScoreStream(
  customerId: string,
  handlers: ScoreStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const sleep = (ms: number) =>
    new Promise<void>((resolve, reject) => {
      const t = setTimeout(resolve, ms);
      if (signal) {
        signal.addEventListener("abort", () => {
          clearTimeout(t);
          reject(signal.reason ?? new Error("aborted"));
        }, { once: true });
      }
    });
  const resp = mockScore(customerId);
  handlers.onThinking?.(1);
  await sleep(900);
  for (const s of resp.trace.steps) {
    handlers.onStep?.(s);
    await sleep(250 + Math.random() * 350);
  }
  handlers.onFinal?.(resp);
}

export function mockChat(customerId: string, message: string, pipeline: "context" | "naive") {
  const hero = customerId;
  if (pipeline === "context") {
    if (/travel/i.test(message) && hero === "cust_jane") {
      return {
        answer: "Yes — Jane has a declared trip to Singapore, 10–17 Nov 2026 (in Agent Memory).",
        trace: { llm_model: "stub-deterministic", total_latency_ms: 38, steps: [
          step({ component: "agent_memory", tool: "get_customer_memory", input: { customer_id: hero }, output_summary: "travel_window: Singapore 10–17 Nov 2026.", latency_ms: 12, redis_keys_touched: ["mem:cust_jane"] }),
        ]} as AgentTrace,
      };
    }
    return {
      answer: `Pulled live context for ${hero}. Ask about travel, devices, or spend to see specifics.`,
      trace: { llm_model: "stub-deterministic", total_latency_ms: 28, steps: [
        step({ component: "context_retriever", tool: "get_customer_context", input: { customer_id: hero }, output_summary: "Customer profile fetched.", latency_ms: 28, redis_keys_touched: [`customer:${hero}`] }),
      ]} as AgentTrace,
    };
  }
  return {
    answer: "Based on policy: 'Cross-border card-present transactions must be reviewed against the customer's declared travel and merchant reputation.' (Policy doc — no customer-specific data.)",
    trace: { llm_model: "stub-deterministic", total_latency_ms: 42, steps: [
      step({ component: "policy_rag", tool: "search_policy", input: { query: message }, output_summary: "Returned 3 policy chunks.", latency_ms: 42, redis_keys_touched: ["policy:0117", "policy:0203", "policy:0042"] }),
    ]} as AgentTrace,
  };
}
