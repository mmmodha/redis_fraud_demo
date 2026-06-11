// Shared color tokens for trace components. The hexes here match the existing
// IrisPanel dot palette so the chatbot trace chips read consistently with the
// fraud-score command-center panels.
import type { TraceComponent } from "@/lib/types";

export const COMPONENT_DOT: Record<TraceComponent | "rdi", string> = {
  context_retriever: "bg-[#1FB36B]",
  feature_store: "bg-[#3D8FE6]",
  agent_memory: "bg-[#B36BFF]",
  policy_rag: "bg-[#E2A03F]",
  llm: "bg-redis-hyper",
  rdi: "bg-[#3D8FE6]",
};

// Chip background + border + text tokens, tuned for the dark theme. LLM rows
// are intentionally de-emphasised since they are not the Redis story.
export const COMPONENT_CHIP: Record<TraceComponent, string> = {
  context_retriever:
    "border-[#1FB36B]/60 bg-[#1FB36B]/15 text-[#A6E8C6]",
  feature_store:
    "border-[#3D8FE6]/60 bg-[#3D8FE6]/15 text-[#B9D7F4]",
  agent_memory:
    "border-[#B36BFF]/60 bg-[#B36BFF]/15 text-[#DCC2FF]",
  policy_rag:
    "border-[#E2A03F]/50 bg-[#E2A03F]/10 text-[#F0CB8E]",
  llm:
    "border-redis-border bg-redis-bg-secondary text-redis-text-muted",
};

export const COMPONENT_LABEL: Record<TraceComponent, string> = {
  context_retriever: "Context Retriever",
  feature_store: "Feature Store",
  agent_memory: "Agent Memory",
  policy_rag: "Policy RAG",
  llm: "LLM",
};
