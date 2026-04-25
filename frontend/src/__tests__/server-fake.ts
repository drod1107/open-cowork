/**
 * In-test fake of the OpenCowork backend.
 *
 * Replaces both `globalThis.fetch` (REST) and `globalThis.WebSocket` (chat),
 * holding minimal in-memory state that mirrors the real server. Tests can
 * peek at requests and inject WebSocket events to verify integration without
 * touching the network.
 */
import { vi } from "vitest";

export type Recorded = { method: string; url: string; body?: unknown };

export interface FakeServerState {
  models: { id: string; supports_vision: boolean | null }[];
  selected: string | null;
  config: Record<string, unknown>;
  schedules: Array<{ id: string; description: string; cron: string; next_run: string | null }>;
  modelsCalls: number;
  recorded: Recorded[];
}

export interface InstalledFakeServer {
  state: FakeServerState;
  socket: FakeServerSocket | null;
  /** Wait until at least one WebSocket has been opened by the app. */
  awaitSocket: () => Promise<FakeServerSocket>;
  uninstall: () => void;
}

export class FakeServerSocket {
  static OPEN = 1;
  static CLOSED = 3;
  public readyState = 0;
  public sent: string[] = [];
  public onmessage: ((e: MessageEvent) => void) | null = null;
  public onopen: (() => void) | null = null;
  public onclose: (() => void) | null = null;
  public onerror: ((e: Event) => void) | null = null;
  constructor(public url: string) {}

  open() {
    this.readyState = FakeServerSocket.OPEN;
    this.onopen?.();
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = FakeServerSocket.CLOSED;
    this.onclose?.();
  }
  /** Test helper: emit an event from the server side. */
  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent);
  }
}

export function installFakeServer(
  initial: Partial<FakeServerState> = {},
): InstalledFakeServer {
  const state: FakeServerState = {
    models: initial.models ?? [
      { id: "llama3.1:8b", supports_vision: null },
      { id: "llava:7b", supports_vision: true },
    ],
    selected: initial.selected ?? null,
    config: initial.config ?? defaultConfig(),
    schedules: initial.schedules ?? [],
    modelsCalls: 0,
    recorded: [],
  };

  const sockets: FakeServerSocket[] = [];
  let socketResolver: ((s: FakeServerSocket) => void) | null = null;

  const realFetch = globalThis.fetch;
  const realWS = globalThis.WebSocket;

  globalThis.fetch = vi.fn(async (input, init) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    let body: unknown = undefined;
    if (init?.body) {
      try {
        body = JSON.parse(init.body as string);
      } catch {
        body = init.body;
      }
    }
    state.recorded.push({ method, url, body });
    return handleRequest(state, method, url, body);
  }) as unknown as typeof fetch;

  const FakeWS = class extends FakeServerSocket {
    constructor(url: string) {
      super(url);
      sockets.push(this);
      // We open in a microtask so handler-assignment in connect() lands
      // before onopen fires. Tests `await server.awaitSocket()` and then
      // `await waitFor(...)` for connected state, so React batching is
      // exercised through the testing-library wait loop.
      Promise.resolve().then(() => this.open());
      socketResolver?.(this);
      socketResolver = null;
    }
  };
  (globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket =
    FakeWS as unknown as typeof WebSocket;

  return {
    state,
    get socket() {
      return sockets[sockets.length - 1] ?? null;
    },
    awaitSocket() {
      const last = sockets[sockets.length - 1];
      if (last) return Promise.resolve(last);
      return new Promise<FakeServerSocket>((resolve) => {
        socketResolver = resolve;
      });
    },
    uninstall() {
      globalThis.fetch = realFetch;
      (globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket = realWS;
    },
  };
}

function defaultConfig(): Record<string, unknown> {
  return {
    provider: "ollama",
    base_url: "http://localhost:11434",
    agent: { max_turns: 5, system_prompt: "" },
    runtime: { working_dir: "." },
    permissions: {
      filesystem: { default: "ask", allowed_dirs: [], blocked_dirs: [] },
      shell: {
        default: "ask",
        allowed_commands: ["echo *", "ls*"],
        blocked_commands: ["rm -rf /*"],
      },
      web: { search: "allow", fetch: "ask" },
      browser: { default: "ask" },
      computer_use: { default: "ask" },
      coding: { default: "ask", git_commit: "ask" },
    },
  };
}

function handleRequest(
  state: FakeServerState,
  method: string,
  url: string,
  body: unknown,
): Response {
  const u = new URL(url, "http://localhost");
  const path = u.pathname;

  if (path === "/api/health") return json({ status: "ok" });

  if (path === "/api/models" && method === "GET") {
    state.modelsCalls += 1;
    return json({
      provider: "ollama",
      base_url: "http://localhost:11434",
      models: state.models,
      selected: state.selected,
    });
  }

  if (path === "/api/models/select" && method === "POST") {
    const b = body as { model?: string };
    if (!b?.model) return json({ detail: "missing model" }, 400);
    state.selected = b.model;
    return json({ selected: b.model });
  }

  if (path === "/api/config" && method === "GET") return json(state.config);
  if (path === "/api/config" && method === "PUT") {
    state.config = body as Record<string, unknown>;
    return json({ ok: true });
  }

  if (path === "/api/schedules" && method === "GET") {
    return json({ schedules: state.schedules });
  }
  if (path === "/api/schedules" && method === "POST") {
    const b = body as { description?: string; cron?: string; id?: string };
    if (!b?.description || !b?.cron) return json({ detail: "missing" }, 400);
    const id = b.id ?? `s${state.schedules.length + 1}`;
    const job = { id, description: b.description, cron: b.cron, next_run: null };
    state.schedules.push(job);
    return json(job);
  }
  const m = path.match(/^\/api\/schedules\/(.+)$/);
  if (m && method === "DELETE") {
    const id = m[1];
    const before = state.schedules.length;
    state.schedules = state.schedules.filter((s) => s.id !== id);
    return json({ removed: state.schedules.length < before });
  }

  return json({ detail: "not found" }, 404);
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
