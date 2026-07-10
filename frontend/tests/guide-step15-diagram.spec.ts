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

test.describe("Guide step 15 diagram", () => {
  test("chat-compare renders context retriever animation", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("guide-mode-toggle").click();

    // Steps 1–13: continue / run as needed (analyst summary gate on step 6).
    for (let i = 0; i < 13; i++) {
      await guideAdvance(page);
    }

    // Step 14: click first chat prompt (event advance)
    await page.locator('[data-guide="chat-prompt-0"]').click({ timeout: 15_000 });

    await expect(page.getByText("Step 15 of")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Same LLM, different answer quality")).toBeVisible();
    const diagram = page.getByTestId("guide-iris-diagram-context-retriever");
    await expect(diagram).toBeVisible();
    await expect(diagram.locator("svg")).toBeVisible({ timeout: 10_000 });
  });
});
