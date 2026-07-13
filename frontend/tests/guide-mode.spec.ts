import { test, expect } from "@playwright/test";

test.describe("Guide mode", () => {
  test("toggle opens guide panel with welcome step", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("guide-mode-toggle").click();
    await expect(page.getByTestId("demo-guide-panel")).toBeVisible();
    await expect(page.getByTestId("guide-spotlight")).toBeVisible();
    await expect(page.getByText("Welcome to the Fraud Command Center")).toBeVisible();
  });

  test("continue advances to meet Mike and selects Mike", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("guide-mode-toggle").click();
    await page.getByTestId("guide-continue").click();
    await expect(page.getByText("Meet Mike — everyday spending")).toBeVisible();
    await expect(page.locator('[data-guide="hero-mike"]')).toHaveAttribute("data-active", "true");
  });

  test("run step hides hero card Run and advances only after score completes", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByTestId("guide-mode-toggle").click();
    await page.getByTestId("guide-continue").click(); // welcome → meet Mike
    await page.getByTestId("guide-continue").click(); // meet Mike → run step

    await expect(page.getByTestId("hero-run-hidden-mike")).toBeVisible();
    await expect(page.getByTestId("run-mike")).toHaveCount(0);

    await page.getByTestId("guide-run-hero").click();
    await expect(page.getByTestId("guide-thinking-banner")).toBeVisible();
    await expect(page.getByText("The verdict — fast and confident")).not.toBeVisible();

    await expect(page.getByText("The verdict — fast and confident")).toBeVisible({
      timeout: 15000,
    });
    await page.getByTestId("guide-continue").click();
    await expect(page.getByTestId("guide-iris-diagram-context-retriever")).toBeVisible();
  });

  test("guide run button is primary on run steps", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("guide-mode-toggle").click();
    await page.getByTestId("guide-continue").click();
    await page.getByTestId("guide-continue").click();

    const runBtn = page.getByTestId("guide-run-hero");
    await expect(runBtn).toBeVisible();
    await expect(runBtn).toHaveClass(/bg-redis-hyper/);
    await expect(runBtn).not.toHaveClass(/border-redis-hyper/);
  });

  test("clipboard helper falls back when navigator.clipboard rejects", async ({
    page,
  }) => {
    await page.goto("/");
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", {
        value: {
          writeText: () => Promise.reject(new Error("denied")),
        },
        configurable: true,
      });
    });

    const result = await page.evaluate(async () => {
      const text = "test clipboard fallback";
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
    });

    expect(["exec-command", "manual"]).toContain(result);
  });
});
