import { useEffect, useMemo, useRef, useState } from "react";
import type { AgentEvent, AgentSocket } from "../lib/ws";
import { api } from "../lib/api";

type ChatItem =
  | { kind: "user"; text: string; id: string }
  | { kind: "assistant"; text: string; id: string }
  | {
      kind: "tool";
      tool: string;
      input: Record<string, unknown>;
      output?: Record<string, unknown>;
      id: string;
    }
  | {
      kind: "permission";
      id: string;
      category: string;
      action: string;
      description: string;
      resolved?: string;
    }
  | { kind: "error"; text: string; id: string };

export interface ChatProps {
  socket: AgentSocket;
  connected?: boolean;
  sessionId?: string | null;
  onSessionId?: (id: string) => void;
  onSessionTitle?: (id: string, title: string) => void;
  onFirstMessage?: (text: string) => void;
  loadedItems?: ChatItem[];
  errors?: string[];
  onAddError?: (msg: string) => void;
}

export default function Chat({ socket, connected = true, sessionId, onSessionId, onSessionTitle, onFirstMessage, loadedItems, errors = [], onAddError }: ChatProps) {
  const [items, setItems] = useState<ChatItem[]>(loadedItems ?? []);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [localLogs, setLocalLogs] = useState<string[]>([]);
  const localLogsRef = useRef<string[]>([]);
  const debugLogs = useMemo(() => [...errors, ...localLogs], [errors, localLogs]);
  const [skillSuggestions, setSkillSuggestions] = useState<Array<{ name: string; description: string }>>([]);
  const [allSkills, setAllSkills] = useState<Array<{ name: string; description: string }>>([]);
  const assistantBufRef = useRef<string>("");
  const currentAssistantId = useRef<string | null>(null);
  const pendingSkillRef = useRef<string | null>(null);
  const busySinceRef = useRef<number>(0);
  const busyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevLoadedItemsRef = useRef<ChatItem[] | undefined>(loadedItems);
  const MIN_BUSY_MS = 500;

  useEffect(() => {
    if (loadedItems !== undefined && loadedItems !== prevLoadedItemsRef.current) {
      setItems(loadedItems);
      setBusy(false);
      assistantBufRef.current = "";
      currentAssistantId.current = null;
    }
    prevLoadedItemsRef.current = loadedItems;
  }, [loadedItems]);

  useEffect(() => {
    api.listSkills().then((r) => setAllSkills(r.skills)).catch(() => {});
  }, []);

  useEffect(() => {
    const off = socket.on((ev: AgentEvent) => {
      handleEvent(ev);
    });
    return () => {
      off();
      if (busyTimeoutRef.current) {
        clearTimeout(busyTimeoutRef.current);
        busyTimeoutRef.current = null;
      }
    };
  }, [socket]);

  const pushLog = (msg: string) => {
    const ts = new Date().toISOString().slice(11, 19);
    const entry = `[${ts}] ${msg}`;
    localLogsRef.current = [...localLogsRef.current, entry];
    setLocalLogs(localLogsRef.current);
    onAddError?.(entry);
  };

  const handleEvent = (ev: AgentEvent) => {
    if (ev.type === "token") {
      const currentText = assistantBufRef.current + ev.text;
      assistantBufRef.current = currentText;
      if (!currentAssistantId.current) {
        const id = crypto.randomUUID();
        currentAssistantId.current = id;
        setItems((items) => [
          ...items,
          { kind: "assistant", text: currentText, id },
        ]);
      } else {
        const id = currentAssistantId.current;
        setItems((items) =>
          items.map((it) =>
            it.kind === "assistant" && it.id === id
              ? { ...it, text: currentText }
              : it,
          ),
        );
      }
  } else if (ev.type === "final") {
    currentAssistantId.current = null;
    assistantBufRef.current = "";
    const elapsed = Date.now() - busySinceRef.current;
    if (elapsed < MIN_BUSY_MS) {
      if (busyTimeoutRef.current) clearTimeout(busyTimeoutRef.current);
      busyTimeoutRef.current = setTimeout(() => {
        setBusy(false);
        busyTimeoutRef.current = null;
      }, MIN_BUSY_MS - elapsed);
    } else {
      setBusy(false);
    }
    } else if (ev.type === "tool_call") {
      const id = crypto.randomUUID();
      setItems((items) => [
        ...items,
        { kind: "tool", tool: ev.tool, input: ev.input, id },
      ]);
    } else if (ev.type === "tool_result") {
      setItems((items) => {
        for (let i = items.length - 1; i >= 0; i--) {
          const it = items[i];
          if (it.kind === "tool" && it.tool === ev.tool && !it.output) {
            const copy = [...items];
            copy[i] = { ...it, output: ev.output };
            return copy;
          }
        }
        return items;
      });
    } else if (ev.type === "permission_request") {
      setItems((items) => [
        ...items,
        {
          kind: "permission",
          id: ev.request.id,
          category: ev.request.category,
          action: ev.request.action,
          description: ev.request.description,
        },
      ]);
    } else if (ev.type === "permission_resolved") {
      setItems((items) =>
        items.map((it) =>
          it.kind === "permission" && it.id === ev.id
            ? { ...it, resolved: ev.ok ? "approved" : "denied" }
            : it,
        ),
      );
    } else if (ev.type === "error") {
      setBusy(false);
      const id = crypto.randomUUID();
      pushLog(ev.error);
      setItems((items) => [
        ...items,
        { kind: "error", text: ev.error, id },
      ]);
    } else if (ev.type === "session_id") {
      onSessionId?.(ev.session_id);
      const pendingSkill = pendingSkillRef.current;
      if (pendingSkill) {
        pendingSkillRef.current = null;
        api.useSkill(ev.session_id, pendingSkill).then((r) => {
          const id = crypto.randomUUID();
          setItems((items) => [...items, { kind: "assistant", text: `Skill "${r.activated}" activated for this session.`, id }]);
        }).catch((e) => {
          const id = crypto.randomUUID();
          setItems((items) => [...items, { kind: "error", text: e.message, id }]);
        });
      }
    } else if (ev.type === "session_title") {
      onSessionTitle?.(ev.session_id, ev.title);
    } else if (ev.type === "close") {
      const detail = ev.reason ? ` (code ${ev.code}: ${ev.reason})` : ` (code ${ev.code})`;
      pushLog(`WebSocket disconnected${detail}`);
    } else if (ev.type === "open") {
      if (localLogsRef.current.length > 0) {
        pushLog("WebSocket reconnected");
      }
    }
  };

  const send = () => {
    if (!input.trim()) return;
    const useSkillMatch = input.trim().match(/^\/use-skill\s+(\S+)\s*$/);
    if (useSkillMatch) {
      const skillName = useSkillMatch[1];
      if (!sessionId) {
        pendingSkillRef.current = skillName;
        const itemId = crypto.randomUUID();
        setItems((items) => [...items, { kind: "user", text: input, id: itemId }]);
        socket.send({ type: "chat", text: `Activating skill: ${skillName}` });
      } else {
        api.useSkill(sessionId, skillName).then((r) => {
          const id = crypto.randomUUID();
          setItems((items) => [...items, { kind: "assistant", text: `Skill "${r.activated}" activated for this session.`, id }]);
        }).catch((e) => {
          const id = crypto.randomUUID();
          const msg = e instanceof Error ? e.message : String(e);
          pushLog(`Skill activation failed: ${msg}`);
          setItems((items) => [...items, { kind: "error", text: msg, id }]);
        });
      }
      setInput("");
      setSkillSuggestions([]);
      return;
    }
    const id = crypto.randomUUID();
    onFirstMessage?.(input.trim());
    setItems((items) => [...items, { kind: "user", text: input, id }]);
    const msg: { type: "chat"; text: string; session_id?: string } = { type: "chat", text: input };
    if (sessionId) msg.session_id = sessionId;
    const sent = socket.send(msg);
    if (!sent) {
      pushLog("Message queued — WebSocket not connected, will send on reconnect");
    }
    setInput("");
    setBusy(true);
    busySinceRef.current = Date.now();
    assistantBufRef.current = "";
    currentAssistantId.current = null;
  };

  const stop = () => {
    socket.send({ type: "stop" });
    if (busyTimeoutRef.current) {
      clearTimeout(busyTimeoutRef.current);
      busyTimeoutRef.current = null;
    }
    setBusy(false);
  };

  const respondPermission = (id: string, decision: string) => {
    socket.send({ type: "permission_response", id, decision });
    setItems((items) =>
      items.map((it) =>
        it.kind === "permission" && it.id === id
          ? { ...it, resolved: decision }
          : it,
      ),
    );
  };

  const copyDebug = () => {
    navigator.clipboard.writeText(debugLogs.join("\n"));
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {!connected && (
        <div className="bg-red-900/60 text-red-100 text-xs text-center py-1.5 flex-shrink-0" data-testid="ws-disconnected-banner">
          Disconnected — reconnecting… Check bug bar (⚙) for details.
        </div>
      )}
      {/* Chat history - scrollable */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-3" ref={bottomRef} data-testid="chat-messages">
        {items.map((it) => (
          <ChatCard key={it.id} item={it} onPermission={respondPermission} />
        ))}
      </div>

      {/* Debug bar */}
      {debugOpen && (
        <div className="bg-red-900/90 text-red-100 text-xs p-2 flex items-start gap-2 max-h-32 overflow-y-auto">
          <button
            className="flex-shrink-0 bg-red-700 hover:bg-red-600 rounded px-2 py-1 text-xs"
            onClick={copyDebug}
            title="Copy all debug output"
          >
            Copy
          </button>
          <pre className="whitespace-pre-wrap flex-1">{debugLogs.join("\n")}</pre>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-slate-700 p-3 pb-2 space-y-2 flex-shrink-0">
        <div className="flex gap-2 items-end">
          <div className="flex-1 relative">
          <textarea
            className="w-full bg-slate-800 rounded-md p-2 text-sm text-slate-100 outline-none border border-slate-600 focus:border-sky-500 resize-none"
            rows={3}
            placeholder="Ask OpenCowork… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={(e) => {
              const val = e.target.value;
              setInput(val);
              if (val.startsWith("/use-skill ")) {
                const query = val.slice("/use-skill ".length).toLowerCase();
                setSkillSuggestions(allSkills.filter((s) => s.name.toLowerCase().includes(query)));
              } else {
                setSkillSuggestions([]);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            data-testid="chat-input"
          />
          {skillSuggestions.length > 0 && (
                <div className="absolute bottom-full left-0 mb-1 bg-slate-700 border border-slate-600 rounded-md shadow-lg max-h-32 overflow-y-auto z-10" data-testid="skill-suggestions">
              {skillSuggestions.map((s) => (
                <button
                  key={s.name}
                  className="block w-full text-left px-3 py-1.5 text-xs hover:bg-slate-600"
                  onClick={() => {
                    setInput(`/use-skill ${s.name} `);
                    setSkillSuggestions([]);
                  }}
                >
                  <span className="font-mono text-sky-300">{s.name}</span>
                  <span className="text-slate-400 ml-2">{s.description}</span>
                </button>
              ))}
            </div>
          )}
          </div>
<div className="flex flex-col gap-1 relative">
      <button
        className="bg-sky-600 hover:bg-sky-500 text-white rounded-md px-3 py-2 text-sm h-1/2 disabled:opacity-50"
          onClick={send}
          disabled={busy || !input.trim()}
          data-testid="send-btn"
      >
        Send
      </button>
      {busy && (
        <button
          className="absolute top-0 left-0 right-0 bg-red-600 hover:bg-red-500 text-white rounded-md px-3 py-2 text-sm h-1/2"
          onClick={stop}
          data-testid="stop-btn"
        >
          Stop
        </button>
      )}
        <button
          className="relative text-slate-500 hover:text-slate-300 h-1/4 text-xs"
          onClick={() => setDebugOpen((o) => !o)}
          title="Toggle debug bar"
          data-testid="debug-toggle"
        >
          ⚙
          {debugLogs.length > 0 && !debugOpen && (
            <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] rounded-full w-3.5 h-3.5 flex items-center justify-center" data-testid="debug-badge">
              {debugLogs.length}
            </span>
          )}
        </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatCard({
  item,
  onPermission,
}: {
  item: ChatItem;
  onPermission: (id: string, decision: string) => void;
}) {
  if (item.kind === "user") {
    return (
      <div className="text-right" data-testid="chat-message-user">
        <div className="inline-block bg-sky-600 rounded-xl px-3 py-2 text-sm max-w-[90%] whitespace-pre-wrap text-white">
          {item.text}
        </div>
      </div>
    );
  }
  if (item.kind === "assistant") {
    return (
      <div data-testid="chat-message-assistant">
        <div className="inline-block bg-slate-700 rounded-xl px-3 py-2 text-sm max-w-[90%] whitespace-pre-wrap text-slate-100">
          {item.text}
        </div>
      </div>
    );
  }
  if (item.kind === "tool") {
    return (
      <div className="border border-slate-600 rounded-xl bg-slate-800 text-xs" data-testid="chat-message-tool">
        <div className="px-3 py-2">
          <span className="font-semibold text-sky-300">{item.tool}</span>
          <pre className="mt-1 bg-slate-950 rounded p-2 overflow-x-auto text-slate-300 max-w-full">
            {JSON.stringify(item.input, null, 2)}
          </pre>
        </div>
        {item.output && (
          <div className="px-3 pb-3">
            <pre className="bg-slate-950 rounded p-2 overflow-x-auto text-slate-300 max-w-full">
              {JSON.stringify(item.output, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  }
  if (item.kind === "error") {
    return (
      <div className="bg-red-900/30 border-2 border-red-500 rounded-xl p-4 text-sm text-red-100 font-medium" data-testid="chat-message-error">
        [error] {item.text}
      </div>
    );
  }
  // permission
  const resolved = item.resolved;
  return (
      <div className="border border-amber-500 rounded-xl p-3 bg-amber-900/30 text-sm" data-testid="permission-request-card">
      <div className="font-semibold text-amber-300" data-testid="permission-request-category">
        Permission request: {item.category}
      </div>
      <div className="font-mono text-xs mt-1 text-amber-100 break-all">
        {item.action}
      </div>
      <div className="text-amber-100/70 mt-1">{item.description}</div>
      {!resolved ? (
        <div className="flex flex-wrap gap-2 mt-2">
          {(["this time", "always", "no", "never"] as const).map((d) => (
          <button
            key={d}
                  className="text-xs bg-slate-700 hover:bg-slate-600 rounded-md px-2 py-1"
            onClick={() => onPermission(item.id, d)}
            data-testid={`permission-btn-${d.replace(/\s/g, "-")}`}
          >
            {d}
          </button>
          ))}
        </div>
      ) : (
        <div className="text-xs text-amber-200 mt-2">
          Resolved: <span className="font-mono">{resolved}</span>
        </div>
      )}
    </div>
  );
}
