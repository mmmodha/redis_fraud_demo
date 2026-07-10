// Frozen AgentTrace contract mirrored from Wave 3a Pydantic schema.
// Do not change shapes here without coordinating with the backend.

export type TraceComponent =
  | "context_retriever"
  | "feature_store"
  | "agent_memory"
  | "policy_rag"
  | "llm";

export interface TraceStep {
  component: TraceComponent;
  tool: string;
  input: Record<string, unknown>;
  output_summary: string;
  output_data: Record<string, unknown> | null;
  latency_ms: number;
  redis_keys_touched: string[];
}

export interface AgentTrace {
  steps: TraceStep[];
  total_latency_ms: number;
  llm_model: string;
}

export type Verdict = "approve" | "review" | "block";

export interface ScoreResponse {
  verdict: Verdict;
  confidence: number;
  reason: string;
  trace: AgentTrace;
  // Wave 7n: true when served from the Redis verdict cache.
  cached?: boolean;
  cache_latency_ms?: number | null;
}

export interface VerdictFastResponse {
  verdict: Verdict;
  confidence: number;
  signals: string[];
  total_latency_ms: number;
}

export interface OtpConfirmResponse {
  confirmed: boolean;
  final_verdict: Verdict;
  step_up_used: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  customer_id: string;
  message: string;
  history?: ChatMessage[];
}

export interface ChatResponse {
  answer: string;
  trace: AgentTrace;
  cached?: boolean;
  cache_latency_ms?: number | null;
  cache_backend?: "local" | "langcache" | null;
  cache_match_type?: "exact" | "semantic" | null;
  cache_similarity?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  tokens_saved_input?: number | null;
  tokens_saved_output?: number | null;
}

export interface RdiStatus {
  ok: boolean;
  lag_ms?: number | null;
  lag_seconds?: number | null;
  events_total?: number | null;
  last_event_at?: string | null;
  last_heartbeat_at?: string | null;
  started_at?: string | null;
  error?: string;
}

export interface HeroProfile {
  key: "mike" | "jane" | "alex" | "sarah";
  customer_id: string;
  card_id: string;
  cardLast4: string;
  name: string;
  firstName: string;
  bio: string;
  scenario: string;
  expectedVerdict: Verdict;
  homeCity: string;
  homeCountry: string;
  transaction: {
    amount: number;
    currency: string;
    merchant_id: string;
    merchant_name: string;
    country: string;
    city: string;
    is_foreign: boolean;
    is_card_present: boolean;
  };
}
