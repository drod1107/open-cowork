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
  | { type: "pong" };

export type OutgoingMessage =
  | { type: "chat"; text: string }
  | { type: "permission_response"; id: string; decision: string }
  | { type: "ping" };

export class AgentSocket {
  private ws: WebSocket | null = null;
  private listeners = new Set<(ev: AgentEvent) => void>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private url: string;

  constructor(url?: string) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    this.url = url ?? `${proto}//${window.location.host}/ws`;
  }

  connect() {
    if (this.ws && this.ws.readyState <= 1) return;
    this.ws = new WebSocket(this.url);
    this.ws.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data) as AgentEvent;
        this.listeners.forEach((fn) => fn(ev));
      } catch {
        /* ignore malformed frames */
      }
    };
    this.ws.onclose = () => {
      if (this.reconnectTimer) return;
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 1500);
    };
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  on(fn: (ev: AgentEvent) => void) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  send(msg: OutgoingMessage) {
    if (!this.ws || this.ws.readyState !== 1) return false;
    this.ws.send(JSON.stringify(msg));
    return true;
  }
}
