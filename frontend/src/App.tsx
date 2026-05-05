import { useEffect, useMemo, useState } from "react";
import Chat from "./components/Chat";
import HistoryTab from "./components/HistoryTab";
import Permissions from "./components/Permissions";
import ModelPicker from "./components/ModelPicker";
import { AgentSocket } from "./lib/ws";
import { api } from "./lib/api";

type Tab = "chat" | "history" | "settings";

type LoadedSession = {
  id: string;
  messages: Array<{ role: string; content: string }>;
  metadata: { title?: string };
};

export default function App() {
  const socket = useMemo(() => new AgentSocket(), []);
  const [tab, setTab] = useState<Tab>("chat");
  const [connected, setConnected] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadedSession, setLoadedSession] = useState<LoadedSession | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [sessionTitle, setSessionTitle] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");

  useEffect(() => {
    const off = socket.on((ev) => {
      if (ev.type === "open") setConnected(true);
      if (ev.type === "close") setConnected(false);
    });
    socket.connect();
    return () => {
      off();
      socket.disconnect();
    };
  }, [socket]);

  useEffect(() => {
    const hash = window.location.hash;
    const match = hash.match(/^#session=(.+)$/);
    if (match) {
      const sessionId = match[1];
      api.getSession(sessionId).then((session) => {
        setLoadedSession(session as unknown as LoadedSession);
        setActiveSessionId(sessionId);
        setSessionTitle(session.metadata?.title || null);
      }).catch(() => {
        window.location.hash = "";
      });
    }
  }, []);

  const handleSessionId = (id: string) => {
    setActiveSessionId(id);
    window.location.hash = `session=${id}`;
  };

  const handleSessionTitle = (_id: string, title: string) => {
    setSessionTitle(title);
    setHistoryRefreshKey((k) => k + 1);
  };

  const handleHistorySelect = async (id: string) => {
    try {
      const session = await api.getSession(id);
      setLoadedSession(session as unknown as LoadedSession);
      setActiveSessionId(id);
      setSessionTitle(session.metadata?.title || null);
      setTab("chat");
      window.location.hash = `session=${id}`;
    } catch {
      setTab("chat");
    }
  };

  const handleHistoryDelete = async (id: string) => {
    try {
      await api.deleteSession(id);
      if (activeSessionId === id) {
        setActiveSessionId(null);
        setLoadedSession(null);
        setSessionTitle(null);
        window.location.hash = "";
      }
      setHistoryRefreshKey((k) => k + 1);
    } catch {
    }
  };

  const saveTitle = async (title: string) => {
    if (!activeSessionId) return;
    const trimmed = title.trim();
    try {
      await fetch(`/api/sessions/${activeSessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metadata: { title: trimmed } }),
      });
      setSessionTitle(trimmed || null);
      setEditingTitle(false);
      setHistoryRefreshKey((k) => k + 1);
    } catch {
      setEditingTitle(false);
    }
  };

  const startEditTitle = () => {
    setTitleInput(sessionTitle || "");
    setEditingTitle(true);
  };

  const cancelEditTitle = () => {
    setEditingTitle(false);
  };

  const handleFirstMessage = (text: string) => {
    if (!activeSessionId || sessionTitle) return;
    const autoTitle = text.length > 50 ? text.slice(0, 50).replace(/\s+\S*$/, "") : text;
    void saveTitle(autoTitle);
  };

  const chatItems = loadedSession
    ? loadedSession.messages.map((m, i) => ({
        kind: m.role === "user" ? ("user" as const) : ("assistant" as const),
        text: m.content,
        id: `loaded-${i}`,
      }))
    : undefined;

  return (
    <div className="h-full flex flex-col">
      {/* Top bar - only show on chat tab for now */}
      {tab === "chat" && (
  <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="font-semibold tracking-tight">OpenCowork</div>
          <ModelPicker onChange={setSelectedModel} />
          {activeSessionId && !editingTitle && (
            <span
              className="text-xs text-slate-300 cursor-pointer hover:text-sky-300 truncate max-w-[200px]"
              onClick={startEditTitle}
              data-testid="session-title-display"
              title="Click to edit title"
            >
              {sessionTitle || "Untitled"}
            </span>
          )}
          {activeSessionId && editingTitle && (
            <input
              className="bg-slate-900 border border-sky-700 rounded px-2 py-0.5 text-xs text-slate-100 outline-none w-[200px]"
              value={titleInput}
              onChange={(e) => setTitleInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveTitle(titleInput);
                if (e.key === "Escape") cancelEditTitle();
              }}
              onBlur={() => saveTitle(titleInput)}
              autoFocus
              data-testid="session-title-input"
            />
          )}
          <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                connected ? "bg-emerald-700/40 text-emerald-200" : "bg-red-800/40 text-red-200"
              }`}
              data-testid="ws-status"
            >
              {connected ? "connected" : "disconnected"}
            </span>
          </div>
        </header>
      )}

    {/* Main content area - scrollable */}
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className={tab === "chat" ? "h-full" : "hidden"}>
        <Chat socket={socket} hasModel={!!selectedModel} sessionId={activeSessionId} onSessionId={handleSessionId} onSessionTitle={handleSessionTitle} onFirstMessage={handleFirstMessage} loadedItems={chatItems} />
      </div>
      {tab === "history" && <HistoryTab onSelect={handleHistorySelect} onDelete={handleHistoryDelete} refreshKey={historyRefreshKey} />}
      {tab === "settings" && <Permissions />}
    </div>

      {/* Bottom tab bar - fixed */}
      <nav className="flex border-t border-slate-800 bg-slate-900">
        {(["chat", "history", "settings"] as const).map((t) => (
          <button
            key={t}
            className={`flex-1 py-3 text-xs ${tab === t ? "text-sky-400" : "text-slate-500"}`}
            onClick={() => setTab(t)}
            data-testid={`tab-${t}`}
          >
            {t}
          </button>
        ))}
      </nav>
    </div>
  );
}
