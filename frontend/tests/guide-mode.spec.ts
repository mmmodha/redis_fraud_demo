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

  test("run scenario button advances guide on Mike run", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("guide-mode-toggle").click();
    await page.getByTestId("guide-continue").click(); // welcome → meet Mike
    await page.getByTestId("guide-continue").click(); // meet Mike → run step
    await page.getByTestId("guide-run-hero").click();
    await expect(page.getByText("The verdict — fast and confident")).toBeVisible({
      timeout: 15000,
    });
    await page.getByTestId("guide-continue").click();
    await expect(page.getByTestId("guide-iris-diagram-context-retriever")).toBeVisible();
  });
});
