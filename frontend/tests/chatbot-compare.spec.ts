import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const SCREENSHOTS = resolve(__dirname, "../../docs/screenshots");
mkdirSync(SCREENSHOTS, { recursive: true });

test.describe("Chatbot comparison panel", () => {
  test("jane 'any upcoming travel?' → Singapore in context-surface, NOT in naive-rag", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByTestId("hero-card-jane").click();

    await page.getByTestId("chat-prompts").getByText("Any upcoming travel?").click();

    const contextAnswer = page.getByTestId("pane-context-answer");
    const naiveAnswer = page.getByTestId("pane-naive-answer");

    await expect(contextAnswer).not.toHaveText("Thinking…", { timeout: 15_000 });
    await expect(naiveAnswer).not.toHaveText("Thinking…", { timeout: 15_000 });

    const contextText = (await contextAnswer.textContent()) ?? "";
    const naiveText = (await naiveAnswer.textContent()) ?? "";

    expect(contextText, "Context Surface must mention Singapore (from agent memory)").toMatch(
      /singapore/i,
    );
    expect(
      naiveText,
      "Naive RAG must NOT cite Jane-specific travel data (memory / bookings)",
    ).not.toMatch(
      /2099-11-10|cust_jane|jane'?s travel|singapore airlines|marina bay|booked.*singapore/i,
    );
    expect(naiveText, "Naive RAG answer must differ from Context Surface").not.toEqual(
      contextText,
    );

    // Wave 7i.4: markdown bold rendering. The chat_context_surface prompt
    // emits **...** runs and the Prose component must turn them into
    // <strong> elements, with no literal asterisks leaking into the DOM.
    expect(contextText, "answer text must not contain literal '**' once rendered").not.toContain(
      "**",
    );
    await expect(
      contextAnswer.locator("strong"),
      "answer bubble should contain at least one <strong> bolded span",
    ).not.toHaveCount(0);
    await expect(
      contextAnswer.locator("p"),
      "answer bubble should render paragraphs as <p> elements",
    ).not.toHaveCount(0);

    await page.screenshot({
      path: resolve(SCREENSHOTS, "chatbot-comparison.png"),
      fullPage: true,
    });
  });

  test("repeat prompt shows LangCache token savings", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("hero-card-jane").click();
    const prompt = page.getByTestId("chat-prompts").getByText("Any upcoming travel?");
    await prompt.click();
    await expect(page.getByTestId("pane-context-answer")).not.toHaveText("Thinking…", {
      timeout: 15_000,
    });
    await prompt.click();
    await expect(
      page.getByTestId("pane-context").getByTestId("langcache-savings-bar"),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("langcache-session-counter")).toContainText(/tokens saved/i);
  });
});
