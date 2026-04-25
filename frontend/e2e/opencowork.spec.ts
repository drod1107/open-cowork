/**
 * End-to-end tests for OpenCowork running against a real FastAPI server.
 *
 * The Playwright `webServer` config in playwright.config.ts boots the backend
 * automatically. These tests assume the backend is reachable at
 * http://127.0.0.1:7337 and the frontend has been built (FastAPI serves the
 * compiled SPA from frontend/dist).
 *
 * The tests are robust to *not* having a local LLM provider running: they
 * intercept /api/models with a fake response so the full UI flow can be
 * exercised without Ollama / LM Studio / vLLM / SGLang. When you do have a
 * provider running, the same tests pass against the real provider response.
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

test("loads the UI, connects WebSocket, populates the model dropdown", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("OpenCowork")).toBeVisible();
  await expect(page.getByTestId("ws-status")).toHaveText("connected", { timeout: 5_000 });

  const select = page.getByTestId("model-select");
  await expect(select).toBeVisible();
  // Wait for the options to populate.
  await expect(page.locator("option", { hasText: "test-llm:latest" })).toHaveCount(1);
});

test("selecting a model removes the no-model hint", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("no-model-hint")).toBeVisible();
  await page.getByTestId("model-select").selectOption("test-llm:latest");
  await expect(page.getByTestId("no-model-hint")).toHaveCount(0);
});

test("scheduler: create, list, and remove a job round-trips through the real backend", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByTestId("panel-scheduler").click();

  const desc = `e2e-task-${Date.now()}`;
  await page.getByTestId("schedule-description").fill(desc);
  await page.getByTestId("schedule-cron").fill("*/15 * * * *");
  await page.getByTestId("schedule-add").click();

  const row = page.locator(`text=${desc}`).first();
  await expect(row).toBeVisible({ timeout: 5_000 });
  // Cron string must round-trip exactly (regression on field-reordering bug).
  await expect(page.locator("text=*/15 * * * *").first()).toBeVisible();

  await row.locator("xpath=..").locator("xpath=..").getByText("remove").click();
  await expect(row).toHaveCount(0, { timeout: 5_000 });
});

test("permissions: changing the shell default persists to the backend", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("panel-permissions").click();

  const sel = page.getByTestId("perm-default-shell");
  await expect(sel).toBeVisible();
  await sel.selectOption("allow");

  // Reload the panel to confirm the change persisted.
  await page.reload();
  await page.getByTestId("panel-permissions").click();
  await expect(page.getByTestId("perm-default-shell")).toHaveValue("allow");

  // Reset to ask so subsequent runs start clean.
  await page.getByTestId("perm-default-shell").selectOption("ask");
});

test("chat without a selected model surfaces a clear error", async ({ page }) => {
  await page.goto("/");
  // Don't select a model — the FE warning should already be visible.
  await expect(page.getByTestId("no-model-hint")).toBeVisible();

  await page.getByTestId("chat-input").fill("hi there");
  await page.getByTestId("send-btn").click();
  // Even if the backend is asked, it returns an error event that the chat
  // surfaces as an "[error] ..." assistant bubble.
  await expect(page.locator("text=/\\[error\\]/")).toBeVisible({ timeout: 5_000 });
});

test("panel switcher mounts each side panel", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("scheduler")).toBeVisible();

  await page.getByTestId("panel-permissions").click();
  await expect(page.getByTestId("permissions")).toBeVisible();

  await page.getByTestId("panel-computer").click();
  await expect(page.getByTestId("computer-view")).toBeVisible();

  await page.getByTestId("panel-scheduler").click();
  await expect(page.getByTestId("scheduler")).toBeVisible();
});
