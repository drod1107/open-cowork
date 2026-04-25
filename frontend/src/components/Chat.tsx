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
    };

export interface ChatProps {
  socket: AgentSocket;
  hasModel?: boolean;
}

export default function Chat({ socket, hasModel = true }: ChatProps) {
  const [items, setItems] = useState<ChatItem[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const assistantBufRef = useRef<string>("");
  const currentAssistantId = useRef<string | null>(null);

  useEffect(() => {
    const off = socket.on((ev: AgentEvent) => handleEvent(ev));
    return () => {
      off();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        // attach output to the most recent tool call with this name
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
            ? { ...it, resolved: "resolved" }
            : it,
        ),
      );
    } else if (ev.type === "error") {
      setBusy(false);
      const id = crypto.randomUUID();
      setItems((items) => [
        ...items,
        { kind: "assistant", text: `[error] ${ev.error}`, id },
      ]);
    }
  };

  const send = () => {
    if (!input.trim()) return;
    const id = crypto.randomUUID();
    setItems((items) => [...items, { kind: "user", text: input, id }]);
    socket.send({ type: "chat", text: input });
    setInput("");
    setBusy(true);
    assistantBufRef.current = "";
    currentAssistantId.current = null;
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

  return (
    <div className="flex flex-col h-full" data-testid="chat">
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {items.map((it) => (
          <ChatCard key={it.id} item={it} onPermission={respondPermission} />
        ))}
        {busy && <div className="text-slate-400 text-sm italic">thinking…</div>}
      </div>
      <div className="border-t border-slate-800 p-3 space-y-2">
        {!hasModel && (
          <div
            className="text-xs text-amber-300 bg-amber-900/20 border border-amber-700 rounded-md px-2 py-1"
            data-testid="no-model-hint"
          >
            Pick a model in the top bar before sending a message.
          </div>
        )}
        <div className="flex gap-2">
          <textarea
            className="flex-1 bg-slate-900 rounded-md p-2 text-sm text-slate-100 outline-none border border-slate-800 focus:border-sky-600 resize-none"
            rows={2}
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
          <button
            className="bg-sky-600 hover:bg-sky-500 text-white rounded-md px-3 text-sm disabled:opacity-50"
            onClick={send}
            disabled={busy || !input.trim()}
            data-testid="send-btn"
          >
            Send
          </button>
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
    return <ToolCard item={item} />;
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
          {(["approve", "deny", "approve-always", "deny-always"] as const).map(
            (d) => (
              <button
                key={d}
                className="text-xs bg-slate-800 hover:bg-slate-700 rounded-md px-2 py-1"
                onClick={() => onPermission(item.id, d)}
              >
                {d}
              </button>
            ),
          )}
        </div>
      ) : (
        <div className="text-xs text-amber-200 mt-2">
          Resolved: <span className="font-mono">{resolved}</span>
        </div>
      )}
    </div>
  );
}

function ToolCard({
  item,
}: {
  item: Extract<ChatItem, { kind: "tool" }>;
}) {
  const [open, setOpen] = useState(false);
  const preview = useMemo(() => JSON.stringify(item.input), [item.input]);
  return (
    <div className="border border-slate-700 rounded-xl bg-slate-900/60 text-xs">
      <button
        className="w-full text-left px-3 py-2 flex justify-between items-center"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="font-semibold text-sky-300">
          {item.tool}
          <span className="text-slate-400 ml-2">{preview}</span>
        </span>
        <span>{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          <pre className="bg-slate-950 rounded p-2 overflow-x-auto">
            {JSON.stringify(item.input, null, 2)}
          </pre>
          {item.output && (
            <pre className="bg-slate-950 rounded p-2 overflow-x-auto">
              {JSON.stringify(item.output, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
