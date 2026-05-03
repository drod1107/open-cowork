import { useEffect, useMemo, useState } from "react";
import Chat from "./components/Chat";
import HistoryTab from "./components/HistoryTab";
import Permissions from "./components/Permissions";
import ModelPicker from "./components/ModelPicker";
import { AgentSocket } from "./lib/ws";

type Tab = "chat" | "history" | "settings";

export default function App() {
  const socket = useMemo(() => new AgentSocket(), []);
  const [tab, setTab] = useState<Tab>("chat");
  const [connected, setConnected] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);

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

  return (
    <div className="h-full flex flex-col">
      {/* Top bar - only show on chat tab for now */}
      {tab === "chat" && (
        <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="font-semibold tracking-tight">OpenCowork</div>
            <ModelPicker onChange={setSelectedModel} />
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
        {tab === "chat" && <Chat socket={socket} hasModel={!!selectedModel} />}
        {tab === "history" && <HistoryTab onSelect={(id) => {
          // Switch to chat tab and load session
          setTab("chat");
          // TODO: Load session history
        }} onDelete={(id) => {
          // TODO: Call API to delete session
          console.log("Delete session", id);
        }} />}
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
