import { test, expect, type Page } from "@playwright/test";

/** Advance one guide step — waits for score/OTP gates before clicking Continue. */
async function guideAdvance(page: Page) {
  const runBtn = page.getByTestId("guide-run-hero");
  if (await runBtn.isVisible()) {
    await runBtn.click();
  }
  const cont = page.getByTestId("guide-continue");
  await expect(cont).toBeVisible({ timeout: 45_000 });
  await cont.click();
}

test.describe("Guide chat-compare diagram", () => {
  test("chat-compare renders context retriever animation", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("guide-mode-toggle").click();

    // Steps 1–11: continue / run through Jane panels (one fewer after meet+run merge).
    for (let i = 0; i < 11; i++) {
      await guideAdvance(page);
    }

    // Step 12: click first chat prompt (event advance)
    await page.locator('[data-guide="chat-prompt-0"]').click({ timeout: 15_000 });

    await expect(page.getByText("Step 13 of")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Same LLM, different answer quality")).toBeVisible();
    const diagram = page.getByTestId("guide-iris-diagram-context-retriever");
    await expect(diagram).toBeVisible();
    await expect(diagram.locator("svg")).toBeVisible({ timeout: 10_000 });
  });
});
