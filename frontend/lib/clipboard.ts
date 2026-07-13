export type CopyResult = "clipboard-api" | "exec-command" | "manual";

/** Copy text with fallbacks for non-HTTPS / restricted clipboard contexts. */
export async function copyToClipboard(text: string): Promise<CopyResult> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return "clipboard-api";
    } catch {
      /* fall through */
    }
  }

  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    if (ok) return "exec-command";
  } catch {
    /* fall through */
  }

  return "manual";
}
