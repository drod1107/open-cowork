import { useEffect, useMemo, useState } from "react";
import Chat from "./components/Chat";
import ModelPicker from "./components/ModelPicker";
import SchedulerPanel from "./components/Scheduler";
import Permissions from "./components/Permissions";
import ComputerView from "./components/ComputerView";
import { AgentSocket } from "./lib/ws";

type Panel = "scheduler" | "permissions" | "computer";

export default function App() {
  const socket = useMemo(() => new AgentSocket(), []);
  const [panel, setPanel] = useState<Panel>("scheduler");
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
        <div className="flex gap-1 text-xs">
          {(["scheduler", "permissions", "computer"] as const).map((p) => (
            <button
              key={p}
              className={`px-2 py-1 rounded-md ${panel === p ? "bg-sky-700" : "bg-slate-800 hover:bg-slate-700"}`}
              onClick={() => setPanel(p)}
              data-testid={`panel-${p}`}
            >
              {p}
            </button>
          ))}
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 md:grid-cols-[1fr_22rem] min-h-0">
        <section className="border-r border-slate-800 min-h-0">
          <Chat socket={socket} hasModel={!!selectedModel} />
        </section>
        <aside className="overflow-y-auto bg-slate-900/40">
          {panel === "scheduler" && <SchedulerPanel />}
          {panel === "permissions" && <Permissions />}
          {panel === "computer" && <ComputerView socket={socket} />}
        </aside>
      </div>
    </div>
  );
}
