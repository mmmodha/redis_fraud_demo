# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: hero-scenarios.spec.ts >> Hero scenarios light up IRIS panels >> alex → verdict block, scenario-specific IRIS panels populated
- Location: tests/hero-scenarios.spec.ts:48:9

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: expect(locator).toHaveAttribute(expected) failed

Locator:  getByTestId('analyst-summary-card')
Expected: "false"
Received: "true"

Call log:
  - Expect "toHaveAttribute" with timeout 60000ms
  - waiting for getByTestId('analyst-summary-card')
    63 × locator resolved to <div data-loading="true" data-testid="analyst-summary-card" class="rounded-redis border border-redis-border-secondary bg-redis-bg-tertiary/40 p-6">…</div>
       - unexpected value "true"

```

```yaml
- text: Analyst summary
```

# Test source

```ts
  1  | import { test, expect, Page } from "@playwright/test";
  2  | import { mkdirSync } from "node:fs";
  3  | import { resolve } from "node:path";
  4  | 
  5  | // Each hero's frozen storyboard lights up a different subset of IRIS panels.
  6  | // `irisPanels` lists the panels that MUST have ≥1 populated item for that
  7  | // scenario (others may legitimately stay in their idle/empty state).
  8  | const HEROES = [
  9  |   {
  10 |     key: "mike",
  11 |     verdict: "approve",
  12 |     irisPanels: ["iris-panel-feature_store", "iris-panel-context_retriever"],
  13 |   },
  14 |   {
  15 |     key: "jane",
  16 |     verdict: "approve",
  17 |     irisPanels: [
  18 |       "iris-panel-context_retriever",
  19 |       "iris-panel-agent_memory",
  20 |     ],
  21 |   },
  22 |   {
  23 |     key: "alex",
  24 |     verdict: "block",
  25 |     irisPanels: ["iris-panel-feature_store", "iris-panel-context_retriever"],
  26 |   },
  27 | ] as const;
  28 | 
  29 | const SCREENSHOTS = resolve(__dirname, "../../docs/screenshots");
  30 | mkdirSync(SCREENSHOTS, { recursive: true });
  31 | 
  32 | async function waitForStaggeredSteps(page: Page) {
  33 |   // Wave 7j: trace strip is wired to /agent/score/stream so the first event
  34 |   // (a "thinking" pulse or the first tool step) must paint within 5s of the
  35 |   // Run click \u2014 long before the full agent loop completes.
  36 |   await expect(page.getByTestId("trace-strip")).toBeVisible({ timeout: 5_000 });
  37 |   // Wait for the stream to drain: AnalystSummary card flips data-loading to
  38 |   // "false" inside `onFinal`, after the last step has been pushed.
> 39 |   await expect(page.getByTestId("analyst-summary-card")).toHaveAttribute(
     |                                                          ^ Error: expect(locator).toHaveAttribute(expected) failed
  40 |     "data-loading",
  41 |     "false",
  42 |     { timeout: 60_000 },
  43 |   );
  44 | }
  45 | 
  46 | test.describe("Hero scenarios light up IRIS panels", () => {
  47 |   for (const hero of HEROES) {
  48 |     test(`${hero.key} → verdict ${hero.verdict}, scenario-specific IRIS panels populated`, async ({ page }) => {
  49 |       await page.goto("/");
  50 |       await expect(page.getByTestId(`hero-card-${hero.key}`)).toBeVisible();
  51 |       await page.getByTestId(`run-${hero.key}`).click();
  52 | 
  53 |       const verdict = page.getByTestId("verdict-card");
  54 |       await expect(verdict).toBeVisible({ timeout: 15_000 });
  55 |       await expect(verdict).toHaveAttribute("data-verdict", hero.verdict);
  56 |       await waitForStaggeredSteps(page);
  57 | 
  58 |       // Trace strip has ≥ 1 step.
  59 |       const traceItems = page.getByTestId("trace-strip").locator("li");
  60 |       await expect(traceItems.first()).toBeVisible();
  61 |       expect(await traceItems.count()).toBeGreaterThanOrEqual(1);
  62 | 
  63 |       // All four IRIS panels must render (even if some sit in the idle state
  64 |       // for this scenario — that's the demo story).
  65 |       for (const id of [
  66 |         "iris-panel-rdi",
  67 |         "iris-panel-feature_store",
  68 |         "iris-panel-context_retriever",
  69 |         "iris-panel-agent_memory",
  70 |       ]) {
  71 |         await expect(page.getByTestId(id)).toBeVisible();
  72 |       }
  73 | 
  74 |       // Scenario-specific panels MUST be populated (not the empty placeholder).
  75 |       for (const id of hero.irisPanels) {
  76 |         const panel = page.getByTestId(id);
  77 |         const populated = await panel
  78 |           .locator(":scope li, :scope [data-testid='iris-memory-doc']")
  79 |           .count();
  80 |         expect(
  81 |           populated,
  82 |           `panel ${id} should have ≥1 populated item for hero ${hero.key}`,
  83 |         ).toBeGreaterThanOrEqual(1);
  84 |       }
  85 |     });
  86 |   }
  87 | 
  88 |   test("Command Center screenshot (jane scenario)", async ({ page }) => {
  89 |     await page.goto("/");
  90 |     await page.getByTestId("run-jane").click();
  91 |     await expect(page.getByTestId("verdict-card")).toBeVisible({ timeout: 15_000 });
  92 |     await waitForStaggeredSteps(page);
  93 |     await page.screenshot({
  94 |       path: resolve(SCREENSHOTS, "command-center.png"),
  95 |       fullPage: true,
  96 |     });
  97 |   });
  98 | });
  99 | 
```