export type AgentEvent =
  | { type: "token"; text: string }
  | { type: "final"; text: string }
  | { type: "tool_call"; tool: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool: string; output: Record<string, unknown> }
  | {
      type: "permission_request";
      request: { id: string; category: string; action: string; description: string };
    }
  | { type: "permission_resolved"; id: string; ok: boolean }
  | { type: "error"; error: string }
  | { type: "session_id"; session_id: string }
  | { type: "session_title"; session_id: string; title: string }
  | { type: "pong" }
  | { type: "open" }
  | { type: "close"; code: number; reason: string };

export type OutgoingMessage =
  | { type: "chat"; text: string; session_id?: string }
  | { type: "stop" }
  | { type: "permission_response"; id: string; decision: string }
  | { type: "ping" };

const PING_INTERVAL = 15_000;

export class AgentSocket {
  private ws: WebSocket | null = null;
  private listeners = new Set<(ev: AgentEvent) => void>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private outbox: OutgoingMessage[] = [];
  private url: string;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
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

  private startPing() {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === 1) {
        this.ws.send(JSON.stringify({ type: "ping" }));
      }
    }, PING_INTERVAL);
  }

  private stopPing() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
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
      this.startPing();
    };
    ws.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data) as AgentEvent;
        this.emitLocal(ev);
      } catch {
        /* ignore malformed frames */
      }
    };
  ws.onclose = (e) => {
      this.connected = false;
      this.stopPing();
      this.emitLocal({ type: "close", code: e.code, reason: e.reason });
      if (this.reconnectTimer) return;
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 1500);
    };
    ws.onerror = (e) => {
      const msg = e instanceof ErrorEvent ? e.message : "WebSocket error";
      this.emitLocal({ type: "error", error: `WebSocket connection error: ${msg}` });
      try {
        ws.close();
      } catch {
        /* noop */
      }
    };
  }

  disconnect() {
    this.stopPing();
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

  send(msg: OutgoingMessage): boolean {
    if (this.ws && this.ws.readyState === 1) {
      this.ws.send(JSON.stringify(msg));
      return true;
    }
    if (!this.ws || this.ws.readyState >= 2) this.connect();
    this.outbox.push(msg);
    return false;
  }

  private emitLocal(ev: AgentEvent) {
    this.listeners.forEach((fn) => fn(ev));
  }
}
