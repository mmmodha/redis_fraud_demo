"use client";
import { useEffect, useState } from "react";

export function JsonTree({
  data,
  defaultOpen = false,
  forceExpand = false,
  highlightKeys,
}: {
  data: unknown;
  defaultOpen?: boolean;
  forceExpand?: boolean;
  highlightKeys?: string[];
}) {
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
      <Node
        data={data as Record<string, unknown> | unknown[]}
        depth={0}
        defaultOpen={defaultOpen}
        forceExpand={forceExpand}
        highlightKeys={highlightKeys}
      />
    </div>
  );
}

function keyMatches(key: string, patterns: string[] | undefined): boolean {
  if (!patterns?.length) return false;
  const lower = key.toLowerCase();
  return patterns.some((p) => lower.includes(p.toLowerCase()));
}

function Node({
  data,
  depth,
  defaultOpen,
  forceExpand,
  highlightKeys,
}: {
  data: Record<string, unknown> | unknown[];
  depth: number;
  defaultOpen: boolean;
  forceExpand: boolean;
  highlightKeys?: string[];
}) {
  const [open, setOpen] = useState(defaultOpen || forceExpand || depth < 1);

  useEffect(() => {
    if (forceExpand) setOpen(true);
  }, [forceExpand]);

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
          {entries.map(([k, v]) => {
            const keyHit = keyMatches(k, highlightKeys);
            return (
              <li
                key={k}
                className={`min-w-0 max-w-full whitespace-pre-wrap break-all py-0.5 ${
                  keyHit ? "font-semibold text-redis-hyper" : ""
                }`}
              >
                <span className={keyHit ? "text-redis-hyper" : "text-redis-text-muted"}>
                  {k}:
                </span>{" "}
                {v !== null && typeof v === "object" ? (
                  <Node
                    data={v as Record<string, unknown>}
                    depth={depth + 1}
                    defaultOpen={defaultOpen}
                    forceExpand={forceExpand}
                    highlightKeys={highlightKeys}
                  />
                ) : (
                  <span className="whitespace-pre-wrap break-all text-redis-text">
                    {typeof v === "string" ? `"${v}"` : String(v)}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
