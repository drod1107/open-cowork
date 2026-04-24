import { describe, it, expect, vi, beforeEach } from "vitest";
import { AgentSocket } from "../lib/ws";

class FakeWS {
  static instances: FakeWS[] = [];
  public readyState = 0;
  public onmessage: ((e: MessageEvent) => void) | null = null;
  public onclose: (() => void) | null = null;
  public sent: string[] = [];
  constructor(public url: string) {
    FakeWS.instances.push(this);
    queueMicrotask(() => {
      this.readyState = 1;
    });
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
    this.onclose?.();
  }
}

describe("AgentSocket", () => {
  beforeEach(() => {
    FakeWS.instances = [];
    // @ts-expect-error override global
    globalThis.WebSocket = FakeWS;
    (globalThis as unknown as { window: { location: Location } }).window = {
      // @ts-expect-error partial Location is fine for our test
      location: { protocol: "http:", host: "localhost:5173" },
    };
  });

  it("dispatches parsed events to listeners", async () => {
    const sock = new AgentSocket();
    const events: unknown[] = [];
    sock.on((ev) => events.push(ev));
    sock.connect();
    await Promise.resolve();
    const ws = FakeWS.instances[0];
    ws.onmessage?.({ data: JSON.stringify({ type: "pong" }) } as MessageEvent);
    expect(events).toContainEqual({ type: "pong" });
  });

  it("queues reconnect on close", async () => {
    vi.useFakeTimers();
    const sock = new AgentSocket();
    sock.connect();
    await Promise.resolve();
    const ws = FakeWS.instances[0];
    ws.close();
    vi.advanceTimersByTime(1500);
    expect(FakeWS.instances.length).toBe(2);
    vi.useRealTimers();
  });
});
