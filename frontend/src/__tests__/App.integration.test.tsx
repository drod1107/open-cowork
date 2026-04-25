/**
 * Full <App/> integration tests.
 *
 * Mounts the real App, with both REST and WebSocket replaced by an in-memory
 * fake. Verifies the full user flow:
 *   1. The app connects, fetches models, exposes them in the picker.
 *   2. Selecting a model POSTs /api/models/select and unlocks the chat.
 *   3. Chat messages are sent over the (queued) WebSocket once open.
 *   4. Streaming token / tool / final events render correctly.
 *   5. Permission requests render an approval card and the response is sent.
 *   6. Switching panels mounts the right surface.
 *   7. Scheduler CRUD round-trips.
 *   8. Permission default toggles persist via PUT /api/config.
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
    expect(screen.getByTestId("no-model-hint")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "hello" },
    });
    expect(send).not.toBeDisabled();

    await selectModel("llama3.1:8b");
    await waitFor(() =>
      expect(screen.queryByTestId("no-model-hint")).not.toBeInTheDocument(),
    );
    const select = await screen.findByTestId("model-select");
    expect(select).toHaveValue("llama3.1:8b");
    expect(server.state.selected).toBe("llama3.1:8b");
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

    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByTestId("send-btn"));
    await waitFor(() => expect(sock.sent.length).toBe(1));

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

  it("renders a permission card and sends the approval back over the socket", async () => {
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
    const before = sock.sent.length;
    fireEvent.click(screen.getByText("approve"));
    await waitFor(() => expect(sock.sent.length).toBeGreaterThan(before));
    const last = JSON.parse(sock.sent[sock.sent.length - 1]);
    expect(last).toEqual({
      type: "permission_response",
      id: "req-1",
      decision: "approve",
    });
  });

  it("error events surface in chat and unblock the send button", async () => {
    render(<App />);
    const sock = await server.awaitSocket();
    await waitFor(() => expect(sock.readyState).toBe(1));

    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "go" },
    });
    fireEvent.click(screen.getByTestId("send-btn"));
    expect(screen.getByTestId("send-btn")).toBeDisabled();

    act(() => {
      sock.emit({ type: "error", error: "no model selected" });
    });

    await waitFor(() =>
      expect(screen.getByText(/\[error\] no model selected/)).toBeInTheDocument(),
    );
    // Button re-enables after error (allowing retry once user types again).
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

describe("App integration: panel switching", () => {
  it("switches from scheduler to permissions to computer view", async () => {
    render(<App />);
    expect(screen.getByTestId("scheduler")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("panel-permissions"));
    await waitFor(() => expect(screen.getByTestId("permissions")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("panel-computer"));
    await waitFor(() => expect(screen.getByTestId("computer-view")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("panel-scheduler"));
    await waitFor(() => expect(screen.getByTestId("scheduler")).toBeInTheDocument());
  });
});

describe("App integration: scheduler CRUD", () => {
  it("creates and deletes a schedule via the panel", async () => {
    render(<App />);
    await screen.findByTestId("scheduler");

    fireEvent.change(screen.getByTestId("schedule-description"), {
      target: { value: "ping cluster" },
    });
    fireEvent.change(screen.getByTestId("schedule-cron"), {
      target: { value: "*/5 * * * *" },
    });
    fireEvent.click(screen.getByTestId("schedule-add"));

    await waitFor(() =>
      expect(server.state.schedules.find((s) => s.description === "ping cluster"))
        .toBeTruthy(),
    );
    await waitFor(() =>
      expect(screen.getByText("ping cluster")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByText("remove"));
    await waitFor(() => expect(server.state.schedules.length).toBe(0));
    await waitFor(() =>
      expect(screen.queryByText("ping cluster")).not.toBeInTheDocument(),
    );
  });
});

describe("App integration: permissions panel", () => {
  it("changes shell default and PUTs the new config", async () => {
    render(<App />);
    fireEvent.click(screen.getByTestId("panel-permissions"));
    const sel = (await screen.findByTestId("perm-default-shell")) as HTMLSelectElement;
    expect(sel.value).toBe("ask");
    fireEvent.change(sel, { target: { value: "allow" } });
    await waitFor(() => {
      const cfg = server.state.config as { permissions: { shell: { default: string } } };
      expect(cfg.permissions.shell.default).toBe("allow");
    });
    const puts = server.state.recorded.filter(
      (r) => r.method === "PUT" && r.url.includes("/api/config"),
    );
    expect(puts.length).toBeGreaterThan(0);
  });

  it("removes a pre-approved shell pattern by clicking the pill", async () => {
    render(<App />);
    fireEvent.click(screen.getByTestId("panel-permissions"));
    await screen.findByTestId("perm-default-shell");
    const pill = await screen.findByText("ls*");
    fireEvent.click(pill);
    await waitFor(() => {
      const cfg = server.state.config as { permissions: { shell: { allowed_commands: string[] } } };
      expect(cfg.permissions.shell.allowed_commands).not.toContain("ls*");
    });
  });
});

describe("App integration: computer view", () => {
  it("renders a screenshot tool_result as an inline image", async () => {
    render(<App />);
    fireEvent.click(screen.getByTestId("panel-computer"));
    const sock = await server.awaitSocket();
    await waitFor(() => expect(sock.readyState).toBe(1));

    const tinyPng =
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";
    act(() => {
      sock.emit({
        type: "tool_result",
        tool: "screenshot",
        output: {
          action: "screenshot",
          ok: true,
          data: { image_base64: tinyPng, mime: "image/png" },
          reason: "ok",
        },
      });
    });

    const view = await screen.findByTestId("computer-view");
    const img = within(view).getByRole("img") as HTMLImageElement;
    await waitFor(() => expect(img.src).toContain("data:image/png;base64"));
  });
});
