import { useEffect, useState } from "react";
import { api, type Schedule } from "../lib/api";

export default function SchedulerPanel() {
  const [items, setItems] = useState<Schedule[]>([]);
  const [description, setDescription] = useState("");
  const [cron, setCron] = useState("0 9 * * *");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const r = await api.listSchedules();
      setItems(r.schedules);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    void load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const submit = async () => {
    setError(null);
    try {
      await api.createSchedule(description, cron);
      setDescription("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const del = async (id: string) => {
    await api.deleteSchedule(id);
    await load();
  };

  return (
    <div className="p-3 space-y-3" data-testid="scheduler">
      <div className="font-semibold">Scheduled tasks</div>
      <div className="space-y-2">
        {items.length === 0 && (
          <div className="text-xs text-slate-500">no scheduled jobs</div>
        )}
        {items.map((s) => (
          <div
            key={s.id}
            className="border border-slate-800 rounded-md p-2 flex justify-between text-xs"
          >
            <div>
              <div className="font-mono">{s.description}</div>
              <div className="text-slate-500">
                {s.cron} • next: {s.next_run || "—"}
              </div>
            </div>
            <button
              className="text-red-400 hover:text-red-300"
              onClick={() => void del(s.id)}
            >
              remove
            </button>
          </div>
        ))}
      </div>
      <div className="border-t border-slate-800 pt-3 space-y-2">
        <input
          className="w-full bg-slate-900 border border-slate-800 rounded-md px-2 py-1 text-xs"
          placeholder="task description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          data-testid="schedule-description"
        />
        <input
          className="w-full bg-slate-900 border border-slate-800 rounded-md px-2 py-1 text-xs font-mono"
          placeholder="cron (min hr dom mon dow)"
          value={cron}
          onChange={(e) => setCron(e.target.value)}
          data-testid="schedule-cron"
        />
        <button
          className="bg-sky-600 hover:bg-sky-500 text-white rounded-md px-3 py-1 text-xs disabled:opacity-50"
          disabled={!description || !cron}
          onClick={submit}
          data-testid="schedule-add"
        >
          add task
        </button>
        {error && <div className="text-red-400 text-xs">{error}</div>}
      </div>
    </div>
  );
}
