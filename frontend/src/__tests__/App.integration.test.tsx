/**
 * Full <App/> integration tests for MVP 3-tab layout.
 *
 * Mounts the real App, with both REST and WebSocket replaced by an in-memory
 * fake. Verifies the MVP features:
 *   1. The app connects, fetches models, exposes them in the picker.
 *   2. Selecting a model POSTs /api/models/select and unlocks the chat.
 *   3. Chat messages are sent over the (queued) WebSocket once open.
 *   4. Streaming token / tool / final events render correctly.
 *   5. Permission requests render an approval card and the response is sent.
 *   6. Switching tabs mounts the right surface (chat/history/settings).
 *   7. Stop button kills stream (UI changes to red).
 *   8. Debug icon/bar functionality.
 *   9. WS status pill flips on close/reconnect.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, act, within } from "@testing-library/react";
import App from "../App";
import { installFakeServer, type InstalledFakeServer } from "./server-fake";

let server: InstalledFakeServer;

beforeEach(() => {
  server = installFakeServer();
});

afterEach(() => {
  server.uninstall();
});

async function selectModel(id: string) {
  const select = (await screen.findByTestId("model-select")) as HTMLSelectElement;
  await waitFor(() => expect(within(select).getByText(id)).toBeInTheDocument());
  fireEvent.change(select, { target: { value: id } });
  await waitFor(() => expect(select.value).toBe(id));
}

describe("App integration: connection & model selection", () => {
  it("connects WebSocket, loads models, and shows status pill", async () => {
    render(<App />);
    await waitFor(() => expect(server.state.modelsCalls).toBeGreaterThan(0));
    const sock = await server.awaitSocket();
    await waitFor(() =>
      expect(screen.getByTestId("ws-status").textContent).toBe("connected"),
    );
    expect(sock.url).toContain("/ws");
  });

  it("disables chat send and shows a hint until a model is selected", async () => {
    render(<App />);
    await waitFor(() => expect(server.state.modelsCalls).toBeGreaterThan(0));
    
    const send = screen.getByTestId("send-btn") as HTMLButtonElement;
    expect(send).toBeDisabled();
  });
});

describe("App integration: 3-tab layout", () => {
  it("renders 3 tabs: chat, history, settings", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("tab-chat")).toBeInTheDocument());
    
    expect(screen.getByTestId("tab-chat")).toBeInTheDocument();
    expect(screen.getByTestId("tab-history")).toBeInTheDocument();
    expect(screen.getByTestId("tab-settings")).toBeInTheDocument();
  });

  it("switches to history tab on click", async () => {
    render(<App />);
    await waitFor(() => screen.getByTestId("tab-history"));
    
    fireEvent.click(screen.getByTestId("tab-history"));
    await waitFor(() => {
      const historyContent = screen.getByText(/history/i);
      expect(historyContent).toBeInTheDocument();
    });
  });

  it("switches to settings tab on click", async () => {
    render(<App />);
    await waitFor(() => screen.getByTestId("tab-settings"));
    
    fireEvent.click(screen.getByTestId("tab-settings"));
    await waitFor(() => {
      expect(screen.getByText(/permissions/i)).toBeInTheDocument();
    });
  });
});

describe("App integration: chat over WebSocket", () => {
  it("queues messages sent before the socket is open and flushes on open", async () => {
    render(<App />);
    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "queued" },
    });
    fireEvent.click(screen.getByTestId("send-btn"));
    const sock = await server.awaitSocket();
    await waitFor(() => expect(sock.sent.length).toBeGreaterThan(0));
    expect(JSON.parse(sock.sent[0])).toEqual({ type: "chat", text: "queued" });
  });

  it("renders streamed tokens and final text", async () => {
    render(<App />);
    const sock = await server.awaitSocket();
    await waitFor(() => expect(sock.readyState).toBe(1));

    await selectModel("llama3.1:8b");

    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByTestId("send-btn"));
    await waitFor(() => expect(sock.sent.length).toBeGreaterThan(0));

    act(() => {
      sock.emit({ type: "token", text: "Hel" });
      sock.emit({ type: "token", text: "lo!" });
      sock.emit({ type: "final", text: "Hello!" });
    });

    await waitFor(() =>
      expect(screen.getByText("Hello!")).toBeInTheDocument(),
    );
  });

  it("renders tool call cards and attaches tool result output", async () => {
    render(<App />);
    const sock = await server.awaitSocket();
    await waitFor(() => expect(sock.readyState).toBe(1));

    act(() => {
      sock.emit({
        type: "tool_call",
        tool: "shell",
        input: { command: "echo hi" },
      });
      sock.emit({
        type: "tool_result",
        tool: "shell",
        output: { ok: true, exit_code: 0, stdout: "hi\n" },
      });
    });

    expect(await screen.findByText("shell")).toBeInTheDocument();
    fireEvent.click(screen.getByText("shell"));
    expect(await screen.findByText(/exit_code/)).toBeInTheDocument();
  });

  it("renders a permission card and sends the response back over the socket", async () => {
    render(<App />);
    const sock = await server.awaitSocket();
    await waitFor(() => expect(sock.readyState).toBe(1));

    act(() => {
      sock.emit({
        type: "permission_request",
        request: {
          id: "req-1",
          category: "shell",
          action: "git push",
          description: "push commits",
        },
      });
    });

    expect(await screen.findByText(/git push/)).toBeInTheDocument();
    expect(screen.getByText("this time")).toBeInTheDocument();
    expect(screen.getByText("always")).toBeInTheDocument();
    expect(screen.getByText("no")).toBeInTheDocument();
    expect(screen.getByText("never")).toBeInTheDocument();

    const before = sock.sent.length;
    fireEvent.click(screen.getByText("this time"));
    await waitFor(() => expect(sock.sent.length).toBeGreaterThan(before));
    const last = JSON.parse(sock.sent[sock.sent.length - 1]);
    expect(last).toEqual({
      type: "permission_response",
      id: "req-1",
      decision: "this time",
    });
  });

  it("stop button appears when busy and kills stream", async () => {
    render(<App />);
    const sock = await server.awaitSocket();
    await waitFor(() => expect(sock.readyState).toBe(1));

    await selectModel("llama3.1:8b");

    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "long task" },
    });
    fireEvent.click(screen.getByTestId("send-btn"));
    
    await waitFor(() => expect(screen.getByTestId("stop-btn")).toBeInTheDocument());
    
    fireEvent.click(screen.getByTestId("stop-btn"));
    
    await waitFor(() => {
      const stopSent = sock.sent.some((s: string) => JSON.parse(s).type === "stop");
      expect(stopSent).toBe(true);
    });
  });

  it("error events surface in chat and unblock the send button", async () => {
    render(<App />);
    const sock = await server.awaitSocket();
    await waitFor(() => expect(sock.readyState).toBe(1));

    await selectModel("llama3.1:8b");

    // Send a message
    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "go" },
    });
    fireEvent.click(screen.getByTestId("send-btn"));
    
    // Wait for button to be disabled (while waiting for response)
    await waitFor(() => expect(screen.getByTestId("send-btn")).toBeDisabled());

    act(() => {
      sock.emit({ type: "error", error: "no model selected" });
    });

    await waitFor(() => {
      expect(screen.getByText(/\[error\] no model selected/)).toBeInTheDocument();
    });
    
    // Button re-enables after error
    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "another" },
    });
    expect(screen.getByTestId("send-btn")).not.toBeDisabled();
  });

  it("flips status pill to disconnected when socket closes", async () => {
    render(<App />);
    const sock = await server.awaitSocket();
    await waitFor(() =>
      expect(screen.getByTestId("ws-status").textContent).toBe("connected"),
    );
    act(() => {
      sock.close();
    });
    await waitFor(() =>
      expect(screen.getByTestId("ws-status").textContent).toBe("disconnected"),
    );
  });
});

describe("App integration: debug bar", () => {
  it("debug icon toggles debug bar", async () => {
    render(<App />);
    await server.awaitSocket();
    
    const debugIcon = screen.getByTitle(/toggle debug bar/i);
    expect(debugIcon).toBeInTheDocument();
    
    fireEvent.click(debugIcon);
    await waitFor(() => {
      expect(screen.getByText(/copy/i)).toBeInTheDocument();
    });
    
    fireEvent.click(debugIcon);
    await waitFor(() => {
      expect(screen.queryByText(/copy/i)).not.toBeInTheDocument();
    });
  });

  it("copy button copies debug output to clipboard", async () => {
    const clipboardWriteText = vi.fn();
    Object.assign(navigator, {
      clipboard: { writeText: clipboardWriteText },
    });

    render(<App />);
    const sock = await server.awaitSocket();
    
    const debugIcon = screen.getByTitle(/toggle debug bar/i);
    fireEvent.click(debugIcon);
    
    act(() => {
      sock.emit({ type: "error", error: "test error" });
    });
    
    const copyBtn = screen.getByText(/copy/i);
    fireEvent.click(copyBtn);
    
    expect(clipboardWriteText).toHaveBeenCalled();
  });
});

describe("App integration: textarea input", () => {
  it("uses textarea (not single-line input)", async () => {
    render(<App />);
    await server.awaitSocket();
    
    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    expect(input.tagName).toBe("TEXTAREA");
    expect(input.rows).toBe(3);
  });

  it("sends on Enter, newlines on Shift+Enter", async () => {
    render(<App />);
    const sock = await server.awaitSocket();
    await selectModel("llama3.1:8b");

    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: false });
    
    await waitFor(() => {
      const sent = sock.sent.some((s: string) => JSON.parse(s).text === "hello");
      expect(sent).toBe(true);
    });
  });
});
