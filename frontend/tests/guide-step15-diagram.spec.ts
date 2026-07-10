import { test, expect } from "@playwright/test";

test.describe("Guide step 15 diagram", () => {
  test("chat-compare renders context retriever animation", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("guide-mode-toggle").click();

    // Steps 1–13: continue / run as needed
    for (let i = 0; i < 13; i++) {
      const runBtn = page.getByTestId("guide-run-hero");
      if (await runBtn.isVisible()) {
        await runBtn.click();
        await expect(page.getByTestId("guide-continue")).toBeVisible({ timeout: 20_000 });
      }
      const cont = page.getByTestId("guide-continue");
      if (await cont.isVisible()) {
        await cont.click();
      }
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
