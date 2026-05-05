/**
 * Settings tab E2E tests
 *
 * Tests provider management, working directory, tool toggles, skills, and permissions.
 */
import { test, expect, type Page } from "@playwright/test";

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

const BASE_CONFIG = {
  provider: "ollama",
  base_url: "http://localhost:11434",
  providers: {
    "ollama": { type: "ollama", base_url: "http://localhost:11434" }
  },
  tools: { shell: false, web: true },
  permissions: {
    web: { fetch_url: "ask", search_web: "ask" },
    shell: { allowed_commands: ["ls*", "pwd", "echo*", "cat*"], blocked_commands: ["rm -rf /*"] }
  },
  skills: { enabled: true, dir: "skills" },
  agent: { max_turns: 50 },
  runtime: { working_dir: "." }
};

test.beforeEach(async ({ page }) => {
  await mockModels(page);
  await page.goto("/");
  await page.getByTestId("tab-settings").click();
});

test.afterEach(async ({ page }) => {
  await page.request.put("http://127.0.0.1:7337/api/config", { data: BASE_CONFIG });
});

test.describe("Provider management", () => {
  test("shows built-in Ollama provider", async ({ page }) => {
    const providerItem = page.getByTestId("provider-item-ollama");
    await expect(providerItem).toBeVisible();
    await expect(providerItem).toContainText("ollama");
  });

  test("add provider form appears when clicking add provider", async ({ page }) => {
    await page.getByTestId("add-provider-btn").click();

    const form = page.getByTestId("add-provider-form");
    await expect(form).toBeVisible();

    await expect(page.getByTestId("provider-type-select")).toBeVisible();
    await expect(page.getByTestId("provider-nickname-input")).toBeVisible();
    await expect(page.getByTestId("provider-baseurl-input")).toBeVisible();
  });

  test("can fill and save new custom provider", async ({ page }) => {
    await page.getByTestId("add-provider-btn").click();

    await page.getByTestId("provider-type-select").selectOption("custom");
    await page.getByTestId("provider-nickname-input").fill("my-custom");
    await page.getByTestId("provider-baseurl-input").fill("https://api.example.com/v1");
    await page.getByTestId("provider-apikey-input").fill("sk-test-key");

    await page.getByTestId("provider-save-btn").click();

    const newProvider = page.getByTestId("provider-item-my-custom");
    await expect(newProvider).toBeVisible();
  });

  test("can cancel add provider form", async ({ page }) => {
    await page.getByTestId("add-provider-btn").click();

    await page.getByTestId("provider-type-select").selectOption("custom");
    await page.getByTestId("provider-nickname-input").fill("test-provider");

    await page.getByTestId("provider-cancel-btn").click();

    const form = page.getByTestId("add-provider-form");
    await expect(form).not.toBeVisible();
  });

  test("can delete custom provider", async ({ page }) => {
    await page.getByTestId("add-provider-btn").click();
    await page.getByTestId("provider-type-select").selectOption("custom");
    await page.getByTestId("provider-nickname-input").fill("to-delete");
    await page.getByTestId("provider-baseurl-input").fill("https://example.com");
    await page.getByTestId("provider-save-btn").click();

    const deleteBtn = page.getByTestId("delete-provider-to-delete");
    await deleteBtn.click();

    const provider = page.getByTestId("provider-item-to-delete");
    await expect(provider).not.toBeVisible();
  });

  test("cannot delete built-in Ollama provider", async ({ page }) => {
    const deleteBtn = page.getByTestId("delete-provider-ollama");
    await expect(deleteBtn).toBeDisabled();
  });
});

test.describe("Working directory", () => {
  test("displays working directory", async ({ page }) => {
    const wdDisplay = page.getByTestId("working-dir-display");
    await expect(wdDisplay).toBeVisible();
  });

  test("edit button shows input field", async ({ page }) => {
    await page.getByTestId("working-dir-edit-btn").click();

    const input = page.getByTestId("working-dir-input");
    await expect(input).toBeVisible();
  });

  test("can save new working directory", async ({ page }) => {
    await page.getByTestId("working-dir-edit-btn").click();
    await page.getByTestId("working-dir-input").fill("/tmp/test-wd");
    await page.getByTestId("working-dir-save-btn").click();

    const display = page.getByTestId("working-dir-display");
    await expect(display).toContainText("/tmp/test-wd");
  });

  test("can cancel working directory edit", async ({ page }) => {
    const originalText = await page.getByTestId("working-dir-display").textContent();

    await page.getByTestId("working-dir-edit-btn").click();
    await page.getByTestId("working-dir-input").fill("/tmp/new-path");
    await page.getByTestId("working-dir-cancel-btn").click();

    const display = page.getByTestId("working-dir-display");
    await expect(display).toHaveText(originalText || "");
  });
});

test.describe("Tool toggles", () => {
  test("shell tool toggle exists", async ({ page }) => {
    const toggle = page.getByTestId("tool-shell-toggle");
    await expect(toggle).toBeVisible();
  });

  test("web tool toggle exists", async ({ page }) => {
    const toggle = page.getByTestId("tool-web-toggle");
    await expect(toggle).toBeVisible();
  });

  test("shell toggle can be switched", async ({ page }) => {
    const toggle = page.getByTestId("tool-shell-toggle");
    const initialState = await toggle.isChecked();

    await toggle.click();

    const newState = await toggle.isChecked();
    expect(newState).not.toBe(initialState);
  });

  test("web toggle can be switched", async ({ page }) => {
    const toggle = page.getByTestId("tool-web-toggle");
    const initialState = await toggle.isChecked();

    await toggle.click();

    const newState = await toggle.isChecked();
    expect(newState).not.toBe(initialState);
  });
});

test.describe("Skills", () => {
  test("skills toggle exists", async ({ page }) => {
    const toggle = page.getByTestId("skills-toggle");
    await expect(toggle).toBeVisible();
  });

  test("skills toggle can be switched", async ({ page }) => {
    const toggle = page.getByTestId("skills-toggle");
    const initialState = await toggle.isChecked();

    await toggle.click();

    const newState = await toggle.isChecked();
    expect(newState).not.toBe(initialState);
  });
});

test.describe("Web permissions", () => {
  test("web fetch_url permission toggle exists", async ({ page }) => {
    const toggle = page.getByTestId("web-perm-fetch_url");
    await expect(toggle).toBeVisible();
  });

  test("web search_web permission toggle exists", async ({ page }) => {
    const toggle = page.getByTestId("web-perm-search_web");
    await expect(toggle).toBeVisible();
  });

  test("web permissions can be cycled through options", async ({ page }) => {
    const toggle = page.getByTestId("web-perm-fetch_url");

    await expect(toggle).toHaveText("ask");
    await toggle.click();
    await expect(toggle).toHaveText("allow");
    await toggle.click();
    await expect(toggle).toHaveText("deny");
  });
});