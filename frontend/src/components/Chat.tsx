import { useEffect, useMemo, useRef, useState } from "react";
import type { AgentEvent, AgentSocket } from "../lib/ws";

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
  hasModel?: boolean;
  sessionId?: string | null;
  onSessionId?: (id: string) => void;
  onSessionTitle?: (id: string, title: string) => void;
  onFirstMessage?: (text: string) => void;
  loadedItems?: ChatItem[];
}

export default function Chat({ socket, hasModel = true, sessionId, onSessionId, onSessionTitle, onFirstMessage, loadedItems }: ChatProps) {
  const [items, setItems] = useState<ChatItem[]>(loadedItems ?? []);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugLogs, setDebugLogs] = useState<string[]>([]);
  const assistantBufRef = useRef<string>("");
  const currentAssistantId = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevLoadedItemsRef = useRef<ChatItem[] | undefined>(loadedItems);

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
    const off = socket.on((ev: AgentEvent) => {
      handleEvent(ev);
    });
    return () => {
      off();
    };
  }, [socket]);

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
      setBusy(false);
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
      setDebugLogs((logs) => [...logs, ev.error]);
      setItems((items) => [
        ...items,
        { kind: "error", text: ev.error, id },
      ]);
    } else if (ev.type === "session_id") {
      onSessionId?.(ev.session_id);
    } else if (ev.type === "session_title") {
      onSessionTitle?.(ev.session_id, ev.title);
    }
  };

  const send = () => {
    if (!input.trim()) return;
    const id = crypto.randomUUID();
    onFirstMessage?.(input.trim());
    setItems((items) => [...items, { kind: "user", text: input, id }]);
    const msg: { type: "chat"; text: string; session_id?: string } = { type: "chat", text: input };
    if (sessionId) msg.session_id = sessionId;
    socket.send(msg);
    setInput("");
    setBusy(true);
    assistantBufRef.current = "";
    currentAssistantId.current = null;
  };

  const stop = () => {
    socket.send({ type: "stop" });
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
    <div className="flex flex-col h-full">
      {/* Chat history - scrollable */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3" ref={bottomRef}>
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
      <div className="border-t border-slate-800 p-3 pb-2 space-y-2">
        {!hasModel && (
          <div className="text-xs text-amber-300 bg-amber-900/20 border border-amber-700 rounded-md px-2 py-1">
            Pick a model in the top bar before sending a message.
          </div>
        )}
        <div className="flex gap-2 items-end">
          <textarea
            className="flex-1 bg-slate-900 rounded-md p-2 text-sm text-slate-100 outline-none border border-slate-800 focus:border-sky-600 resize-none"
            rows={3}
            placeholder="Ask OpenCowork… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            data-testid="chat-input"
          />
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
              className="text-slate-500 hover:text-slate-300 h-1/4 text-xs"
              onClick={() => setDebugOpen((o) => !o)}
              title="Toggle debug bar"
            >
              ⚙
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
      <div className="text-right">
        <div className="inline-block bg-sky-700/40 rounded-xl px-3 py-2 text-sm max-w-[90%] whitespace-pre-wrap">
          {item.text}
        </div>
      </div>
    );
  }
  if (item.kind === "assistant") {
    return (
      <div>
        <div className="inline-block bg-slate-800 rounded-xl px-3 py-2 text-sm max-w-[90%] whitespace-pre-wrap">
          {item.text}
        </div>
      </div>
    );
  }
  if (item.kind === "tool") {
    return (
      <div className="border border-slate-700 rounded-xl bg-slate-900/60 text-xs">
        <div className="px-3 py-2">
          <span className="font-semibold text-sky-300">{item.tool}</span>
          <pre className="mt-1 bg-slate-950 rounded p-2 overflow-x-auto text-slate-300">
            {JSON.stringify(item.input, null, 2)}
          </pre>
        </div>
        {item.output && (
          <div className="px-3 pb-3">
            <pre className="bg-slate-950 rounded p-2 overflow-x-auto text-slate-300">
              {JSON.stringify(item.output, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  }
  if (item.kind === "error") {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-xl p-3 text-sm text-red-200">
        [error] {item.text}
      </div>
    );
  }
  // permission
  const resolved = item.resolved;
  return (
    <div className="border border-amber-600 rounded-xl p-3 bg-amber-900/20 text-sm">
      <div className="font-semibold text-amber-300">
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
              className="text-xs bg-slate-800 hover:bg-slate-700 rounded-md px-2 py-1"
              onClick={() => onPermission(item.id, d)}
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
