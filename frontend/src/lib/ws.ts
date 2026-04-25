export type AgentEvent =
  | { type: "token"; text: string }
  | { type: "final"; text: string }
  | { type: "tool_call"; tool: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool: string; output: Record<string, unknown> }
  | {
      type: "permission_request";
      request: {
        id: string;
        category: string;
        action: string;
        description: string;
      };
    }
  | { type: "permission_resolved"; id: string; ok: boolean }
  | { type: "scheduler_start"; description: string }
  | { type: "scheduler_event"; event: AgentEvent }
  | { type: "scheduler_end"; description: string }
  | { type: "scheduler_error"; error: string }
  | { type: "error"; error: string }
  | { type: "pong" }
  | { type: "open" }
  | { type: "close" };

export type OutgoingMessage =
  | { type: "chat"; text: string }
  | { type: "permission_response"; id: string; decision: string }
  | { type: "ping" };

export class AgentSocket {
  private ws: WebSocket | null = null;
  private listeners = new Set<(ev: AgentEvent) => void>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private outbox: OutgoingMessage[] = [];
  private url: string;
  public connected = false;

  constructor(url?: string) {
    if (url) {
      this.url = url;
    } else if (typeof window !== "undefined" && window.location) {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      this.url = `${proto}//${window.location.host}/ws`;
    } else {
      this.url = "ws://localhost:7337/ws";
    }
  }

  connect() {
    if (this.ws && this.ws.readyState <= 1) return;
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.onopen = () => {
      this.connected = true;
      this.emitLocal({ type: "open" });
      const queued = this.outbox;
      this.outbox = [];
      for (const msg of queued) ws.send(JSON.stringify(msg));
    };
    ws.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data) as AgentEvent;
        this.emitLocal(ev);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      this.connected = false;
      this.emitLocal({ type: "close" });
      if (this.reconnectTimer) return;
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 1500);
    };
    ws.onerror = () => {
      try {
        ws.close();
      } catch {
        /* noop */
      }
    };
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.connected = false;
  }

  on(fn: (ev: AgentEvent) => void) {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  }

  /**
   * Send a message. If the socket isn't open yet, queue it and flush on open.
   * Returns true once sent OR queued, so callers don't need to handle a
   * "not connected" case differently.
   */
  send(msg: OutgoingMessage): boolean {
    if (this.ws && this.ws.readyState === 1) {
      this.ws.send(JSON.stringify(msg));
      return true;
    }
    this.outbox.push(msg);
    if (!this.ws || this.ws.readyState >= 2) this.connect();
    return true;
  }

  private emitLocal(ev: AgentEvent) {
    this.listeners.forEach((fn) => fn(ev));
  }
}
