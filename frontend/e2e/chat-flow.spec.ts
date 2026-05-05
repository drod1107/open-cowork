/**
 * Chat flow E2E tests
 *
 * Tests message sending, skill autocomplete, stop button, and permission requests.
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
}

async function mockNoModel(page: Page) {
  await page.route("**/api/models*", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...FAKE_MODELS, selected: null }),
      });
    } else {
      await route.continue();
    }
  });
}

test.beforeEach(async ({ page }) => {
  await mockModels(page);
  await page.goto("/");
  await page.getByTestId("model-select").selectOption("test-llm:latest");
});

test.describe("Message sending", () => {
  test("sending message creates user bubble", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("Hello world");
    await page.getByTestId("send-btn").click();

    await expect(page.locator("text=Hello world")).toBeVisible();
  });

  test("input clears after sending", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("Test message");
    await page.getByTestId("send-btn").click();

    await expect(input).toHaveValue("");
  });

  test("can send message with Enter key", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("Enter key test");
    await input.press("Enter");

    await expect(page.locator("text=Enter key test")).toBeVisible();
  });

  test("Shift+Enter adds newline instead of sending", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("Line one");
    await input.press("Shift+Enter");

    const value = await input.inputValue();
    expect(value).toContain("Line one");
  });

  test("empty message cannot be sent", async ({ page }) => {
    const sendBtn = page.getByTestId("send-btn");
    await expect(sendBtn).toBeDisabled();
  });

  test("whitespace-only message cannot be sent", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("   ");
    const sendBtn = page.getByTestId("send-btn");
    await expect(sendBtn).toBeDisabled();
  });
});

test.describe("Use-skill command", () => {
  test("typing /use-skill shows skill autocomplete", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("/use-skill ");

    const suggestions = page.locator("text=code-review");
    await expect(suggestions.first()).toBeVisible();
  });

  test("clicking skill suggestion fills input", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("/use-skill ");

    const suggestion = page.locator("button").filter({ hasText: "code-review" }).first();
    await suggestion.click();

    await expect(input).toHaveValue(/code-review/);
  });

  test("/use-skill command shows activation message", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("/use-skill code-review");
    await page.getByTestId("send-btn").click();

    await expect(page.locator('text=Skill "code-review" activated')).toBeVisible({ timeout: 5000 });
  });

  test("skill autocomplete filters by typed text", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("/use-skill code");

    const codeReview = page.locator("text=code-review");
    await expect(codeReview).toBeVisible();

    const writing = page.locator("text=writing");
    await expect(writing).not.toBeVisible();
  });
});

test.describe("Stop button", () => {
  test("stop button appears when agent is busy", async ({ page }) => {
    const input = page.getByTestId("chat-input");
    await input.fill("generate long response");
    await page.getByTestId("send-btn").click();

    const stopBtn = page.getByTestId("stop-btn");
    await expect(stopBtn).toBeVisible({ timeout: 5000 });
  });

  test("stop button appears when sending message", async ({ page }) => {
    await mockModels(page);
    await page.goto("/");
    await page.getByTestId("model-select").selectOption("test-llm:latest");
    await page.waitForTimeout(500);

    const input = page.getByTestId("chat-input");
    await input.fill("test message");
    await page.getByTestId("send-btn").click();

    const stopBtn = page.getByTestId("stop-btn");
    await expect(stopBtn).toBeVisible({ timeout: 5000 });
  });
});

test.describe("No model warning", () => {
  test("warning visible when no model selected", async ({ page }) => {
    await mockNoModel(page);
    await page.goto("/");

    const warning = page.locator("text=Pick a model in the top bar before sending a message.");
    await expect(warning).toBeVisible();
  });

  test("warning disappears after selecting model", async ({ page }) => {
    await mockNoModel(page);
    await page.goto("/");

    const warning = page.locator("text=Pick a model in the top bar before sending a message.");
    await expect(warning).toBeVisible();

    await page.getByTestId("model-select").selectOption("test-llm:latest");

    await expect(warning).not.toBeVisible();
  });
});

test.describe("Chat input states", () => {
  test("warning shows when no model", async ({ page }) => {
    await mockNoModel(page);
    await page.goto("/");

    const warning = page.locator("text=Pick a model in the top bar before sending a message.");
    await expect(warning).toBeVisible();
  });
});