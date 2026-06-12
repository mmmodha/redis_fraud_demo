import { test, expect, Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

// Each hero's frozen storyboard lights up a different subset of IRIS panels.
// `irisPanels` lists the panels that MUST have ≥1 populated item for that
// scenario (others may legitimately stay in their idle/empty state).
const HEROES = [
  {
    key: "mike",
    verdict: "approve",
    irisPanels: ["iris-panel-feature_store", "iris-panel-context_retriever"],
  },
  {
    key: "jane",
    verdict: "approve",
    irisPanels: [
      "iris-panel-context_retriever",
      "iris-panel-agent_memory",
    ],
  },
  {
    key: "alex",
    verdict: "block",
    irisPanels: ["iris-panel-feature_store", "iris-panel-context_retriever"],
  },
] as const;

const SCREENSHOTS = resolve(__dirname, "../../docs/screenshots");
mkdirSync(SCREENSHOTS, { recursive: true });

async function waitForStaggeredSteps(page: Page) {
  // Wave 7j: trace strip is wired to /agent/score/stream so the first event
  // (a "thinking" pulse or the first tool step) must paint within 5s of the
  // Run click \u2014 long before the full agent loop completes.
  await expect(page.getByTestId("trace-strip")).toBeVisible({ timeout: 5_000 });
  // Wait for the stream to drain: AnalystSummary card flips data-loading to
  // "false" inside `onFinal`, after the last step has been pushed.
  await expect(page.getByTestId("analyst-summary-card")).toHaveAttribute(
    "data-loading",
    "false",
    { timeout: 60_000 },
  );
}

test.describe("Hero scenarios light up IRIS panels", () => {
  for (const hero of HEROES) {
    test(`${hero.key} → verdict ${hero.verdict}, scenario-specific IRIS panels populated`, async ({ page }) => {
      await page.goto("/");
      await expect(page.getByTestId(`hero-card-${hero.key}`)).toBeVisible();
      await page.getByTestId(`run-${hero.key}`).click();

      const verdict = page.getByTestId("verdict-card");
      await expect(verdict).toBeVisible({ timeout: 15_000 });
      await expect(verdict).toHaveAttribute("data-verdict", hero.verdict);
      await waitForStaggeredSteps(page);

      // Trace strip has ≥ 1 step.
      const traceItems = page.getByTestId("trace-strip").locator("li");
      await expect(traceItems.first()).toBeVisible();
      expect(await traceItems.count()).toBeGreaterThanOrEqual(1);

      // All four IRIS panels must render (even if some sit in the idle state
      // for this scenario — that's the demo story).
      for (const id of [
        "iris-panel-rdi",
        "iris-panel-feature_store",
        "iris-panel-context_retriever",
        "iris-panel-agent_memory",
      ]) {
        await expect(page.getByTestId(id)).toBeVisible();
      }

      // Scenario-specific panels MUST be populated (not the empty placeholder).
      for (const id of hero.irisPanels) {
        const panel = page.getByTestId(id);
        const populated = await panel
          .locator(":scope li, :scope [data-testid='iris-memory-doc']")
          .count();
        expect(
          populated,
          `panel ${id} should have ≥1 populated item for hero ${hero.key}`,
        ).toBeGreaterThanOrEqual(1);
      }
    });
  }

  test("Command Center screenshot (jane scenario)", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("run-jane").click();
    await expect(page.getByTestId("verdict-card")).toBeVisible({ timeout: 15_000 });
    await waitForStaggeredSteps(page);
    await page.screenshot({
      path: resolve(SCREENSHOTS, "command-center.png"),
      fullPage: true,
    });
  });
});
