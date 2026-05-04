/**
 * Full <App/> integration tests using REAL server.
 * Starts/stops the backend automatically - no dev team participation needed.
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act, within } from "@testing-library/react";
import App from "../App";
import { setupTestServer, getServerUrl, isServerReady } from "./server-test-harness";

// Setup server for all tests
setupTestServer();

describe("App integration: connection & model selection", () => {
  it("connects to real server and loads models", async () => {
    render(<App />);
    
    // Wait for app to connect to real server
    await waitFor(() => {
      const status = screen.getByTestId("ws-status");
      expect(status.textContent).toBe("connected");
    }, { timeout: 10000 });
    
    // Model picker should have options from real server
    const select = (await screen.findByTestId("model-select")) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBeGreaterThan(0));
  });

  it("disables chat send until model is selected", async () => {
    render(<App />);
    
    await waitFor(() => {
      expect(screen.getByTestId("ws-status").textContent).toBe("connected");
    }, { timeout: 10000 });
    
    const send = screen.getByTestId("send-btn") as HTMLButtonElement;
    expect(send).toBeDisabled();
  });
});

describe("App integration: 3-tab layout", () => {
  it("renders 3 tabs: chat, history, settings", async () => {
    render(<App />);
    
    await waitFor(() => screen.getByTestId("tab-chat"));
    
    expect(screen.getByTestId("tab-chat")).toBeInTheDocument();
    expect(screen.getByTestId("tab-history")).toBeInTheDocument();
    expect(screen.getByTestId("tab-settings")).toBeInTheDocument();
  });
});
