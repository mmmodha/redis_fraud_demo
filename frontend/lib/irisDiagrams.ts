export type IrisDiagramSlug = "rdi" | "context-retriever" | "agent-memory" | "langcache";

export type IrisDiagramPanel = {
  slug: IrisDiagramSlug;
  title: string;
  subtitle: string;
  lottiePath: string;
};

export const IRIS_DIAGRAM_PANELS: IrisDiagramPanel[] = [
  {
    slug: "rdi",
    title: "Redis Data Integration",
    subtitle: "Streams Postgres / Kafka changes into Redis in real time",
    lottiePath: "/iris/rdi.json",
  },
  {
    slug: "context-retriever",
    title: "Context Retriever",
    subtitle: "Pulls fresh customer + transaction context for every decision",
    lottiePath: "/iris/context-retriever.json",
  },
  {
    slug: "agent-memory",
    title: "Agent Memory",
    subtitle: "Persists short-term + long-term agent state across turns",
    lottiePath: "/iris/agent-memory.json",
  },
  {
    slug: "langcache",
    title: "LangCache",
    subtitle: "Semantic cache for repeated LLM prompts to cut latency and cost",
    lottiePath: "/iris/langcache.json",
  },
];

export function irisDiagramBySlug(slug: IrisDiagramSlug): IrisDiagramPanel {
  const panel = IRIS_DIAGRAM_PANELS.find((p) => p.slug === slug);
  if (!panel) throw new Error(`Unknown IRIS diagram slug: ${slug}`);
  return panel;
}
