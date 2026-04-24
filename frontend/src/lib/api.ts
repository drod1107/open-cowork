export type Model = { id: string; supports_vision: boolean | null };
export type Schedule = {
  id: string;
  description: string;
  cron: string;
  next_run: string | null;
};

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}

export const api = {
  listModels: (force = false) =>
    fetch(`/api/models?force=${force}`).then((r) =>
      json<{ provider: string; base_url: string; models: Model[]; selected: string | null }>(r),
    ),
  selectModel: (model: string) =>
    fetch("/api/models/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    }).then((r) => json<{ selected: string }>(r)),

  listSchedules: () =>
    fetch("/api/schedules").then((r) => json<{ schedules: Schedule[] }>(r)),
  createSchedule: (description: string, cron: string) =>
    fetch("/api/schedules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description, cron }),
    }).then((r) => json<Schedule>(r)),
  deleteSchedule: (id: string) =>
    fetch(`/api/schedules/${id}`, { method: "DELETE" }).then((r) =>
      json<{ removed: boolean }>(r),
    ),

  readConfig: () => fetch("/api/config").then((r) => json<Record<string, unknown>>(r)),
  writeConfig: (config: Record<string, unknown>) =>
    fetch("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }).then((r) => json<{ ok: boolean }>(r)),
};
