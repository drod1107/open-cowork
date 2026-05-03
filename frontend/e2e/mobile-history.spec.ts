import { test, expect, type Page, type Browser } from "@playwright/test";

const MOBILE_VIEWPORT = { width: 390, height: 844 }; // iPhone 14

async function mockModels(page: Page) {
  await page.route("**/api/models*", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          provider: "ollama",
          base_url: "http://localhost:11434",
          models: [{ id: "test-model", supports_vision: null }],
          selected: "test-model",
        }),
      });
    } else {
      await route.continue();
    }
  });
}

async function mobileContext(browser: Browser) {
  return browser.newContext({ viewport: MOBILE_VIEWPORT });
}

test.describe("Mobile session history", () => {
  test("scroll area has positive clientHeight on mobile", async ({ browser }) => {
    const context = await mobileContext(browser);
    const page = await context.newPage();
    await mockModels(page);

    await page.goto("http://127.0.0.1:7337");
    await page.waitForLoadState("networkidle");

    const scrollArea = page.locator('[data-testid="chat-scroll"]');
    await expect(scrollArea).toBeVisible({ timeout: 5000 });

    const clientHeight = await scrollArea.evaluate((el: HTMLElement) => el.clientHeight);
    console.log(`Chat scroll area clientHeight: ${clientHeight}px`);
    await page.screenshot({ path: "/tmp/mobile-layout.png" });

    expect(clientHeight).toBeGreaterThan(100);
    await context.close();
  });

  test("past user messages are visible after selecting a chat on mobile", async ({ browser }) => {
    const baseURL = "http://127.0.0.1:7337";

    // Find a session with at least one user message
    const { sessions } = await (await fetch(`${baseURL}/api/sessions`)).json() as { sessions: Array<{ id: string; metadata: Record<string, unknown> }> };
    if (sessions.length === 0) {
      test.skip(true, "No sessions to test with");
      return;
    }

    let targetSession: { id: string; metadata: Record<string, unknown> } | null = null;
    let userText = "";

    for (const s of sessions) {
      const detail = await (await fetch(`${baseURL}/api/sessions/${s.id}`)).json() as { messages: Array<Record<string, unknown>> };
      const userMsg = detail.messages.find((m) => m.role === "user");
      if (userMsg && String(userMsg.text ?? "").trim()) {
        targetSession = s;
        userText = String(userMsg.text).slice(0, 40);
        break;
      }
    }

    if (!targetSession) {
      test.skip(true, "No session with user messages found");
      return;
    }

    console.log(`Testing session: "${targetSession.metadata?.title ?? targetSession.id}" — first user msg: "${userText}"`);

    const context = await mobileContext(browser);
    const page = await context.newPage();
    await mockModels(page);

    await page.goto(baseURL);
    await page.waitForLoadState("networkidle");

    // Switch to chats sidebar on mobile
    await page.getByTestId("tab-chats").click();

    // Click the session
    const label = String(targetSession.metadata?.title ?? targetSession.id.slice(0, 8));
    await page.getByText(label).first().click();

    // Wait for scroll area to be visible and content to load
    const scrollArea = page.locator('[data-testid="chat-scroll"]');
    await expect(scrollArea).toBeVisible({ timeout: 5000 });

    // Give React time to fully render items and scroll
    await page.waitForTimeout(200);

    // Verify scroll position
    const scrollMetrics = await scrollArea.evaluate((el: HTMLElement) => ({
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      atBottom: el.scrollHeight - el.scrollTop - el.clientHeight < 50,
    }));
    console.log(`Scroll metrics:`, scrollMetrics);

    // The first user message text must appear somewhere in the scroll area
    await expect(scrollArea.getByText(userText, { exact: false })).toBeVisible({ timeout: 5000 });

    // Count visible user bubbles (with blue background)
    const userBubbles = scrollArea.locator(".bg-sky-700\\/40");
    const userCount = await userBubbles.count();
    console.log(`User message bubbles in DOM: ${userCount}`);

    // Count visible assistant bubbles (with gray background)
    const assistantBubbles = scrollArea.locator(".bg-slate-800.rounded-xl");
    const assistantCount = await assistantBubbles.count();
    console.log(`Assistant message bubbles in DOM: ${assistantCount}`);

    // At least one user bubble must be visible in the viewport
    if (userCount > 0) {
      await expect(userBubbles.first()).toBeVisible({ timeout: 3000 });
    }

    await page.screenshot({ path: "/tmp/mobile-history-after.png" });

    expect(userCount).toBeGreaterThan(0);
    expect(assistantCount).toBeGreaterThan(0);
    await context.close();
  });

  test("URL hash restores session on refresh", async ({ browser }) => {
    const baseURL = "http://127.0.0.1:7337";

    const { sessions } = await (await fetch(`${baseURL}/api/sessions`)).json() as { sessions: Array<{ id: string; metadata: Record<string, unknown> }> };
    if (sessions.length === 0) {
      test.skip(true, "No sessions to test with");
      return;
    }

    // Find a session with a title so we can assert it reloads
    const session = sessions.find((s) => s.metadata?.title) ?? sessions[0];
    const label = String(session.metadata?.title ?? session.id.slice(0, 8));

    const context = await mobileContext(browser);
    const page = await context.newPage();
    await mockModels(page);

    // Navigate directly to the session via URL hash
    await page.goto(`${baseURL}#session=${session.id}`);
    await page.waitForLoadState("networkidle");

    // Session title should be visible in the title bar
    await expect(page.getByTestId("session-title-display")).toContainText(label, { timeout: 5000 });

    // The URL hash should still be set (not wiped on load)
    const hash = await page.evaluate(() => window.location.hash);
    console.log(`URL hash after load: ${hash}`);
    expect(hash).toBe(`#session=${session.id}`);

    await context.close();
  });
});
