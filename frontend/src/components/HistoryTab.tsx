import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface HistoryProps {
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  refreshKey?: number;
}

export default function History({ onSelect, onDelete, refreshKey }: HistoryProps) {
  const [sessions, setSessions] = useState<Array<{
    id: string;
    metadata: { title?: string };
    updated_at: string;
  }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.listSessions()
      .then((data) => setSessions(data.sessions || []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="p-3 text-xs text-slate-500">
      {loading ? (
        <div data-testid="history-loading">Loading…</div>
      ) : sessions.length === 0 ? (
        <div data-testid="no-sessions">No sessions yet</div>
      ) : (
        <div className="space-y-2">
          {sessions.map((session) => (
            <div
              key={session.id}
              className="p-2 border border-slate-800 rounded hover:bg-slate-900 cursor-pointer"
              data-testid={`session-${session.id}`}
              onClick={() => onSelect(session.id)}
            >
              <div className="text-slate-200">
                {session.metadata?.title || "New chat"}
              </div>
              <div className="text-slate-500 text-xs mt-1">
                {formatDate(session.updated_at)}
              </div>
              <button
                className="text-red-400 hover:text-red-300 text-xs mt-1"
                data-testid={`delete-session-${session.id}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(session.id);
                  // Optimistic UI update
                  setSessions((prev) => prev.filter((s) => s.id !== session.id));
                }}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
