"use client";
import { useState } from "react";

export function JsonTree({ data, defaultOpen = false }: { data: unknown; defaultOpen?: boolean }) {
  if (data === null || data === undefined) {
    return <span className="font-redis-mono text-xs text-redis-text-muted">null</span>;
  }
  if (typeof data !== "object") {
    return (
      <span className="block min-w-0 max-w-full whitespace-pre-wrap break-all font-redis-mono text-xs text-redis-text">
        {typeof data === "string" ? `"${data}"` : String(data)}
      </span>
    );
  }
  return (
    <div className="min-w-0 max-w-full">
      <Node data={data as Record<string, unknown> | unknown[]} depth={0} defaultOpen={defaultOpen} />
    </div>
  );
}

function Node({
  data,
  depth,
  defaultOpen,
}: {
  data: Record<string, unknown> | unknown[];
  depth: number;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen || depth < 1);
  const isArr = Array.isArray(data);
  const entries: [string, unknown][] = isArr
    ? (data as unknown[]).map((v, i) => [String(i), v])
    : Object.entries(data as Record<string, unknown>);

  if (entries.length === 0) {
    return <span className="font-redis-mono text-xs text-redis-text-muted">{isArr ? "[]" : "{}"}</span>;
  }
  return (
    <div className="min-w-0 max-w-full font-redis-mono text-xs">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-redis-text-link hover:text-redis-hyper"
      >
        {open ? "▼" : "▶"} {isArr ? `Array(${entries.length})` : `{${entries.length}}`}
      </button>
      {open && (
        <ul className="ml-3 mt-1 min-w-0 max-w-full border-l border-redis-border pl-3">
          {entries.map(([k, v]) => (
            <li key={k} className="min-w-0 max-w-full whitespace-pre-wrap break-all py-0.5">
              <span className="text-redis-text-muted">{k}:</span>{" "}
              {v !== null && typeof v === "object" ? (
                <Node data={v as Record<string, unknown>} depth={depth + 1} defaultOpen={false} />
              ) : (
                <span className="whitespace-pre-wrap break-all text-redis-text">
                  {typeof v === "string" ? `"${v}"` : String(v)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
