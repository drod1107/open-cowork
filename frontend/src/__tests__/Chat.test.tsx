import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import Chat from "../components/Chat";
import type { AgentEvent } from "../lib/ws";

class MockSocket {
  private listeners = new Set<(e: AgentEvent) => void>();
  public sent: unknown[] = [];
  on(fn: (e: AgentEvent) => void) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
  send(msg: unknown) {
    this.sent.push(msg);
    return true;
  }
  emit(e: AgentEvent) {
    this.listeners.forEach((l) => l(e));
  }
  connect() {}
  disconnect() {}
}

describe("Chat", () => {
  it("sends a chat message when Send is clicked", () => {
    const socket = new MockSocket();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<Chat socket={socket as any} />);
    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.click(screen.getByTestId("send-btn"));
    expect(socket.sent).toEqual([{ type: "chat", text: "hello" }]);
  });

  it("streams assistant tokens and renders them together", () => {
    const socket = new MockSocket();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<Chat socket={socket as any} />);
    act(() => {
      socket.emit({ type: "token", text: "Hel" });
      socket.emit({ type: "token", text: "lo!" });
      socket.emit({ type: "final", text: "Hello!" });
    });
    expect(screen.getByText("Hello!")).toBeInTheDocument();
  });

  it("renders a permission card and replies on approve", () => {
    const socket = new MockSocket();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<Chat socket={socket as any} />);
    act(() => {
      socket.emit({
        type: "permission_request",
        request: {
          id: "req-1",
          category: "shell",
          action: "git push",
          description: "push commits",
        },
      });
    });
    expect(screen.getByText(/git push/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("approve"));
    expect(socket.sent).toContainEqual({
      type: "permission_response",
      id: "req-1",
      decision: "approve",
    });
  });
});
