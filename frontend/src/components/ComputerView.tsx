import { useEffect, useState } from "react";
import type { AgentEvent, AgentSocket } from "../lib/ws";

interface Props {
  socket: AgentSocket;
}

export default function ComputerView({ socket }: Props) {
  const [shot, setShot] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);

  useEffect(() => {
    const off = socket.on((ev: AgentEvent) => {
      if (ev.type === "tool_result") {
        const output = ev.output as { data?: { image_base64?: string; mime?: string } };
        const img = output?.data?.image_base64;
        const mime = output?.data?.mime ?? "image/png";
        if (img) setShot(`data:${mime};base64,${img}`);
        setLog((l) =>
          [`${new Date().toLocaleTimeString()} ${ev.tool}`, ...l].slice(0, 50),
        );
      } else if (ev.type === "tool_call") {
        setLog((l) =>
          [`${new Date().toLocaleTimeString()} → ${ev.tool}`, ...l].slice(0, 50),
        );
      }
    });
    return () => {
      off();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [socket]);

  return (
    <div className="p-3 space-y-2 text-xs" data-testid="computer-view">
      <div className="font-semibold">Computer view</div>
      {shot ? (
        <img
          src={shot}
          alt="desktop"
          className="w-full border border-slate-800 rounded-md"
        />
      ) : (
        <div className="text-slate-500">no screenshot yet</div>
      )}
      <div className="border-t border-slate-800 pt-2 space-y-1 max-h-48 overflow-y-auto font-mono">
        {log.map((l, i) => (
          <div key={i} className="text-slate-400">
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}
