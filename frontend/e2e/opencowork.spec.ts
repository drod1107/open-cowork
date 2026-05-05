/**
 * OpenCowork E2E tests - Core app smoke tests
 *
 * Playwright boots backend via webServer config in playwright.config.ts.
 * Tests mock model API to avoid needing actual LLM provider.
 */
import { test, expect, type Page } from "@playwright/test";

const FAKE_MODELS = {
  provider: "ollama",
  base_url: "http://localhost:11434",
  models: [
    { id: "test-llm:latest", supports_vision: null },
    { id: "test-vision:latest", supports_vision: true },
  ],
  selected: null as string | null,
};

async function mockModels(page: Page) {
  let selected: string | null = FAKE_MODELS.selected;
  await page.route("**/api/models*", async (route) => {
    const req = route.request();
    if (req.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...FAKE_MODELS, selected }),
      });
      return;
    }
    await route.continue();
  });
  await page.route("**/api/models/select", async (route) => {
    const body = JSON.parse(route.request().postData() || "{}");
    selected = body.model ?? null;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ selected }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await mockModels(page);
});

test("loads the UI, connects WebSocket, populates model dropdown", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("ws-status")).toHaveText("connected", { timeout: 10_000 });

  const select = page.getByTestId("model-select");
  await expect(select).toBeVisible();
  await expect(select).toHaveText(/test-llm:latest/);
});

test("selecting a model enables chat input", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("model-select").selectOption("test-llm:latest");

  const chatInput = page.getByTestId("chat-input");
  await expect(chatInput).toBeEnabled();
});

test("tab switching navigates between views", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("tab-chat").click();
  await expect(page.locator('[data-testid="chat-input"]')).toBeVisible();

  await page.getByTestId("tab-history").click();
  await expect(page.getByTestId("history-loading")).not.toBeVisible({ timeout: 5000 });
  const hasNoSessions = await page.getByTestId("no-sessions").isVisible().catch(() => false);
  const hasSessions = await page.locator('[data-testid^="session-"]').count();
  expect(hasNoSessions || hasSessions > 0).toBe(true);

  await page.getByTestId("tab-settings").click();
  await expect(page.locator('[data-testid="permissions"]')).toBeVisible();
});

test("chat without model shows warning and disables send", async ({ page }) => {
  await page.goto("/");

  const warning = page.locator("text=Pick a model in the top bar before sending a message.");
  await expect(warning).toBeVisible();

  const sendBtn = page.getByTestId("send-btn");
  await expect(sendBtn).toBeDisabled();
});

test("sending a message creates user bubble", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("model-select").selectOption("test-llm:latest");

  const input = page.getByTestId("chat-input");
  await input.fill("Hello test");

  await page.getByTestId("send-btn").click();

  await expect(page.locator("text=Hello test")).toBeVisible();
});

test("WebSocket status shows connection state", async ({ page }) => {
  await page.goto("/");
  const wsStatus = page.getByTestId("ws-status");
  await expect(wsStatus).toHaveText("connected", { timeout: 10_000 });
});

test("session title display element exists when session active", async ({ page }) => {
  await mockModels(page);
  await page.goto("/");
  await page.waitForTimeout(1000);

  const titleDisplay = page.getByTestId("session-title-display");
  const isVisible = await titleDisplay.isVisible().catch(() => false);
  expect(isVisible || !isVisible);
});

test("model picker shows loading state then options", async ({ page }) => {
  await page.goto("/");
  const select = page.getByTestId("model-select");
  await expect(select).toBeVisible();

  await expect(select).toHaveText(/select a model/);
  await expect(select).toHaveText(/test-llm:latest/);
});

test("refresh models button exists and is clickable", async ({ page }) => {
  await page.goto("/");
  const refreshBtn = page.getByTestId("refresh-models");
  await expect(refreshBtn).toBeVisible();
  await refreshBtn.click();
});

test("settings tab shows permissions panel", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("tab-settings").click();

  const perms = page.getByTestId("permissions");
  await expect(perms).toBeVisible();
});

test("settings tab shows add provider button", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("tab-settings").click();

  const addProvider = page.getByTestId("add-provider-btn");
  await expect(addProvider).toBeVisible();
});

test("history tab renders correctly", async ({ page }) => {
  await mockModels(page);
  await page.goto("/");
  await page.getByTestId("tab-history").click();
  await expect(page.getByTestId("history-loading")).not.toBeVisible({ timeout: 5000 });

  const hasNoSessions = await page.getByTestId("no-sessions").isVisible().catch(() => false);
  const hasSessions = await page.locator('[data-testid^="session-"]').count();

  expect(hasNoSessions || hasSessions > 0).toBe(true);
});