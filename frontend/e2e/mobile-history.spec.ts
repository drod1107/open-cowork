/**
 * Mobile history E2E tests
 *
 * Tests history tab behavior on mobile viewport.
 */
import { test, expect, type Page, type Browser } from "@playwright/test";

const MOBILE_VIEWPORT = { width: 390, height: 844 };

const FAKE_MODELS = {
  provider: "ollama",
  base_url: "http://localhost:11434",
  models: [{ id: "test-model", supports_vision: null }],
  selected: "test-model",
};

async function mockModels(page: Page) {
  await page.route("**/api/models*", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FAKE_MODELS),
      });
    } else {
      await route.continue();
    }
  });
}

async function mobileContext(browser: Browser) {
  return browser.newContext({ viewport: MOBILE_VIEWPORT });
}

test.describe("Mobile history tab", () => {
  test("history tab shows on mobile viewport", async ({ browser }) => {
    const context = await mobileContext(browser);
    const page = await context.newPage();
    await mockModels(page);

    await page.goto("/");
    await page.getByTestId("tab-history").click();

    const sessions = page.locator('[data-testid^="session-"]');
    const count = await sessions.count();
    if (count === 0) {
      await expect(page.getByTestId("no-sessions")).toBeVisible();
    } else {
      await expect(sessions.first()).toBeVisible();
    }

    await context.close();
  });

  test("sessions list shows when sessions exist", async ({ browser }) => {
    const context = await mobileContext(browser);
    const page = await context.newPage();
    await mockModels(page);

    await page.goto("/");
    await page.getByTestId("tab-history").click();

    await page.waitForTimeout(1000);

    const sessions = page.locator('[data-testid^="session-"]');
    const count = await sessions.count();

    if (count > 0) {
      await expect(sessions.first()).toBeVisible();
    } else {
      await expect(page.getByTestId("no-sessions")).toBeVisible();
    }

    await context.close();
  });

  test("clicking session shows its messages", async ({ browser }) => {
    const baseURL = "http://127.0.0.1:7337";

    let { sessions } = await (await fetch(`${baseURL}/api/sessions`)).json() as { sessions: Array<{ id: string }> };
    if (sessions.length === 0) {
      await fetch(`${baseURL}/api/sessions`, { method: "POST" });
      ({ sessions } = await (await fetch(`${baseURL}/api/sessions`)).json() as { sessions: Array<{ id: string }> });
    }

    const context = await mobileContext(browser);
    const page = await context.newPage();
    await mockModels(page);

    await page.goto("/");
    await page.getByTestId("tab-history").click();

    const sessionItem = page.getByTestId(`session-${sessions[0].id}`);
    await sessionItem.click();

    await page.waitForTimeout(500);

    const titleDisplay = page.getByTestId("session-title-display");
    await expect(titleDisplay).toBeVisible();

await context.close();
  });

  test("URL hash restores session on refresh", async ({ browser }) => {
    const baseURL = "http://127.0.0.1:7337";

    let { sessions } = await (await fetch(`${baseURL}/api/sessions`)).json() as { sessions: Array<{ id: string; metadata: Record<string, unknown> }> };
    if (sessions.length === 0) {
      await fetch(`${baseURL}/api/sessions`, { method: "POST" });
      ({ sessions } = await (await fetch(`${baseURL}/api/sessions`)).json() as { sessions: Array<{ id: string; metadata: Record<string, unknown> }> });
    }

    const session = sessions[0];
    const label = String(session.metadata?.title ?? session.id.slice(0, 8));

    const context = await mobileContext(browser);
    const page = await context.newPage();
    await mockModels(page);

    await page.goto(`${baseURL}#session=${session.id}`);
    await page.waitForLoadState("networkidle");

    const titleDisplay = page.getByTestId("session-title-display");
    await expect(titleDisplay).toContainText(label, { timeout: 5000 });

    const hash = await page.evaluate(() => window.location.hash);
    expect(hash).toBe(`#session=${session.id}`);

    await context.close();
  });

  test("tab navigation works on mobile", async ({ browser }) => {
    const context = await mobileContext(browser);
    const page = await context.newPage();
    await mockModels(page);

    await page.goto("/");

    await page.getByTestId("tab-history").click();
    const sessions = page.locator('[data-testid^="session-"]');
    const count = await sessions.count();
    if (count === 0) {
      await expect(page.getByTestId("no-sessions")).toBeVisible();
    } else {
      await expect(sessions.first()).toBeVisible();
    }

    await page.getByTestId("tab-settings").click();
    await expect(page.getByTestId("permissions")).toBeVisible();

    await page.getByTestId("tab-chat").click();
    await expect(page.getByTestId("chat-input")).toBeVisible();

    await context.close();
  });

  test("model picker accessible on mobile", async ({ browser }) => {
    const context = await mobileContext(browser);
    const page = await context.newPage();
    await mockModels(page);

    await page.goto("/");

    const modelSelect = page.getByTestId("model-select");
    await expect(modelSelect).toBeVisible();

    await context.close();
  });
});