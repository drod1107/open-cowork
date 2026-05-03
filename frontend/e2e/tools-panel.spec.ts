import { test, expect, Page, request } from "@playwright/test";

// The server is already running (reused by playwright.config.ts)

async function openToolsPanel(page: Page) {
  await page.goto("/");
  // Desktop: click the "tools" panel button in the header
  await page.getByTestId("panel-tools").click();
}

async function cleanupE2eTools() {
  const ctx = await request.newContext({ baseURL: "http://127.0.0.1:7337" });
  try {
    await ctx.delete("/api/tools/e2e_test_tool");
  } catch { /* ignore if not present */ }
  await ctx.dispose();
}

test.describe("Tools panel", () => {
  test.beforeEach(async () => { await cleanupE2eTools(); });
  test.afterEach(async () => { await cleanupE2eTools(); });
  test("loads and displays built-in tools grouped by category", async ({ page }) => {
    await openToolsPanel(page);

    // Should show loading then the tool list
    await expect(page.getByText("Built-in")).toBeVisible({ timeout: 8000 });

    // Check key groups are present
    await expect(page.getByText("Core", { exact: true })).toBeVisible();
    await expect(page.getByText("Web", { exact: true })).toBeVisible();
    await expect(page.getByText("Files", { exact: true })).toBeVisible();
    await expect(page.getByText("Git", { exact: true })).toBeVisible();

    // Check a handful of specific tools are listed
    await expect(page.getByTestId("tool-row-shell")).toBeVisible();
    await expect(page.getByTestId("tool-row-search_web")).toBeVisible();
    await expect(page.getByTestId("tool-row-read_file")).toBeVisible();
    await expect(page.getByTestId("tool-row-git_commit")).toBeVisible();
    await expect(page.getByTestId("tool-row-browser")).toBeVisible();
  });

  test("shows Custom section even when empty", async ({ page }) => {
    await openToolsPanel(page);
    await expect(page.getByText("Custom", { exact: true })).toBeVisible({ timeout: 8000 });
    await expect(page.getByText(/No custom tools yet/)).toBeVisible();
  });

  test("toggle switches a built-in tool off and back on", async ({ page }) => {
    await openToolsPanel(page);
    await expect(page.getByTestId("tool-row-shell")).toBeVisible({ timeout: 8000 });

    const shellRow = page.getByTestId("tool-row-shell");
    const toggle = shellRow.getByTestId("tool-toggle");

    // Should start enabled (checked)
    await expect(toggle).toHaveAttribute("aria-checked", "true");

    // Toggle off
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    // Row should be dimmed
    await expect(shellRow).toHaveClass(/opacity-40/);

    // Toggle back on
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await expect(shellRow).not.toHaveClass(/opacity-40/);
  });

  test("clicking a tool row opens its edit form", async ({ page }) => {
    await openToolsPanel(page);
    await expect(page.getByTestId("tool-row-shell")).toBeVisible({ timeout: 8000 });

    await page.getByTestId("tool-row-shell").click();

    // Should show the form
    await expect(page.getByTestId("tool-form-name")).toBeVisible();
    await expect(page.getByTestId("tool-form-description")).toBeVisible();

    // Name should be pre-filled and read-only
    const nameInput = page.getByTestId("tool-form-name");
    await expect(nameInput).toHaveValue("shell");
    await expect(nameInput).toBeDisabled();

    // Description should be editable
    const descInput = page.getByTestId("tool-form-description");
    await expect(descInput).not.toBeDisabled();
    await expect(descInput).not.toBeEmpty();

    // Parameters for shell (one: command)
    await expect(page.getByText("command", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Shell command to execute")).toBeVisible();
  });

  test("Cancel button in edit form returns to list", async ({ page }) => {
    await openToolsPanel(page);
    await expect(page.getByTestId("tool-row-shell")).toBeVisible({ timeout: 8000 });

    await page.getByTestId("tool-row-shell").click();
    await expect(page.getByTestId("tool-form-cancel")).toBeVisible();
    await page.getByTestId("tool-form-cancel").click();

    // Back to list
    await expect(page.getByTestId("tool-row-shell")).toBeVisible();
  });

  test("can edit a built-in tool description and save", async ({ page }) => {
    await openToolsPanel(page);
    await expect(page.getByTestId("tool-row-git_status")).toBeVisible({ timeout: 8000 });

    await page.getByTestId("tool-row-git_status").click();

    const desc = page.getByTestId("tool-form-description");
    await desc.clear();
    await desc.fill("Get git status — edited by e2e test");
    await page.getByTestId("tool-form-save").click();

    // Returns to list
    await expect(page.getByTestId("tool-row-git_status")).toBeVisible({ timeout: 5000 });

    // Re-open and verify it persisted
    await page.getByTestId("tool-row-git_status").click();
    await expect(page.getByTestId("tool-form-description")).toHaveValue("Get git status — edited by e2e test");

    // Restore original description
    const descInput = page.getByTestId("tool-form-description");
    await descInput.clear();
    await descInput.fill("Get git status of the working directory.");
    await page.getByTestId("tool-form-save").click();
  });

  test("+ button opens create form with empty name field", async ({ page }) => {
    await openToolsPanel(page);
    await expect(page.getByTestId("add-tool-btn")).toBeVisible({ timeout: 8000 });

    await page.getByTestId("add-tool-btn").click();

    await expect(page.getByTestId("tool-form-name")).toBeVisible();
    await expect(page.getByTestId("tool-form-name")).toBeEmpty();
    await expect(page.getByTestId("tool-form-command")).toBeVisible();
  });

  test("create form auto-slugifies name to display_name", async ({ page }) => {
    await openToolsPanel(page);
    await page.getByTestId("add-tool-btn").click();

    const nameInput = page.getByTestId("tool-form-name");
    await nameInput.fill("my new tool");

    // display_name should auto-populate
    await expect(page.getByTestId("tool-form-display-name")).toHaveValue("my_new_tool");
    // name input should be slugified
    await expect(nameInput).toHaveValue("my_new_tool");
  });

  test("full custom tool lifecycle: create, toggle, delete", async ({ page }) => {
    await openToolsPanel(page);
    await expect(page.getByTestId("add-tool-btn")).toBeVisible({ timeout: 8000 });

    // Create
    await page.getByTestId("add-tool-btn").click();
    await page.getByTestId("tool-form-name").fill("e2e_test_tool");
    await page.getByTestId("tool-form-display-name").fill("E2E Test Tool");
    await page.getByTestId("tool-form-description").fill("Created by playwright e2e test");
    await page.getByTestId("tool-form-command").fill("echo {{message}}");
    await page.getByTestId("tool-form-save").click();

    // Should appear in custom section
    await expect(page.getByTestId("tool-row-e2e_test_tool")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("E2E Test Tool")).toBeVisible();

    // Toggle it off
    const toggle = page.getByTestId("tool-row-e2e_test_tool").getByTestId("tool-toggle");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "false");

    // Open edit and verify the command template and delete it
    await page.getByTestId("tool-row-e2e_test_tool").click();
    await expect(page.getByTestId("tool-form-command")).toHaveValue("echo {{message}}");

    // Delete
    page.on("dialog", (dialog) => dialog.accept());
    await page.getByText("Delete").click();

    // Should be gone from the list
    await expect(page.getByTestId("tool-row-e2e_test_tool")).not.toBeVisible({ timeout: 5000 });
    // Custom section should show empty state again
    await expect(page.getByText(/No custom tools yet/)).toBeVisible();
  });

  test("MCP button opens install form", async ({ page }) => {
    await openToolsPanel(page);
    await expect(page.getByTestId("add-mcp-btn")).toBeVisible({ timeout: 8000 });

    await page.getByTestId("add-mcp-btn").click();

    await expect(page.getByTestId("mcp-source-input")).toBeVisible();
    await expect(page.getByTestId("mcp-install-btn")).toBeVisible();
    await expect(page.getByTestId("mcp-install-btn")).toBeDisabled(); // empty source

    await page.getByTestId("mcp-source-input").fill("https://github.com/example/test");
    await expect(page.getByTestId("mcp-install-btn")).not.toBeDisabled();

    // Cancel goes back
    await page.getByText("Cancel").click();
    await expect(page.getByTestId("tool-row-shell")).toBeVisible();
  });
});
