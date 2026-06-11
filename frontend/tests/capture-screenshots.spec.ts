import { test, expect, Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

// Dedicated capture suite used by scripts/capture-screenshots.sh to produce
// the marketing/runbook PNGs in docs/screenshots/. The hero-scenarios and
// chatbot-compare specs already write command-center.png and
// chatbot-comparison.png as a side-effect; this spec fills in the gaps:
//   - hero-mike.png / hero-jane.png / hero-alex.png  (per-hero command center)
//   - iris-panels-detail.png                          (close-up of the IRIS rail)

const SCREENSHOTS = resolve(__dirname, "../../docs/screenshots");
mkdirSync(SCREENSHOTS, { recursive: true });

async function runHeroAndSettle(page: Page, key: "mike" | "jane" | "alex") {
  await page.goto("/");
  await expect(page.getByTestId(`hero-card-${key}`)).toBeVisible();
  await page.getByTestId(`run-${key}`).click();
  await expect(page.getByTestId("verdict-card")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("trace-strip")).toBeVisible({ timeout: 10_000 });
  // Wait for staggered IRIS panel reveal animations to finish.
  await page.waitForTimeout(1600);
}

test.describe("Capture per-hero screenshots", () => {
  for (const key of ["mike", "jane", "alex"] as const) {
    test(`hero ${key} full-page capture`, async ({ page }) => {
      await runHeroAndSettle(page, key);
      await page.screenshot({
        path: resolve(SCREENSHOTS, `hero-${key}.png`),
        fullPage: true,
      });
    });
  }

  test("IRIS panels detail (jane scenario, rail close-up)", async ({ page }) => {
    await runHeroAndSettle(page, "jane");
    const rail = page.getByTestId("iris-rail");
    await expect(rail).toBeVisible();
    // All four panels rendered before we frame the close-up.
    for (const id of [
      "iris-panel-rdi",
      "iris-panel-feature_store",
      "iris-panel-context_retriever",
      "iris-panel-agent_memory",
    ]) {
      await expect(page.getByTestId(id)).toBeVisible();
    }
    await rail.screenshot({
      path: resolve(SCREENSHOTS, "iris-panels-detail.png"),
    });
  });
});
