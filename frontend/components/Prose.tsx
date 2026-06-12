"use client";
import type { ReactNode } from "react";

// Wave 7i.4: shared dependency-free prose renderer. The LLM emits
// markdown-flavoured text with `**bold**` emphasis and `\n\n` paragraph
// breaks (analyst summary, chatbot answers). Split on blank lines into
// paragraphs and render `**...**` runs as <strong>. Single newlines are
// preserved via `whitespace-pre-line` so list-ish output still wraps
// naturally.
export function Prose({
  text,
  className = "space-y-2",
  testId,
}: {
  text: string;
  className?: string;
  testId?: string;
}) {
  const paragraphs = text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);
  if (paragraphs.length === 0) return null;
  return (
    <div data-testid={testId} className={className}>
      {paragraphs.map((p, i) => (
        <p key={i} className="whitespace-pre-line">
          {renderBoldSpans(p)}
        </p>
      ))}
    </div>
  );
}

function renderBoldSpans(text: string): ReactNode[] {
  // Split on **...** and emit <strong> for the bold runs.
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default Prose;
