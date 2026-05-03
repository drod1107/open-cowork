export type Model = { id: string; supports_vision: boolean | null };

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

  readConfig: () => fetch("/api/config").then((r) => json<Record<string, unknown>>(r)),
  writeConfig: (config: Record<string, unknown>) =>
    fetch("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }).then((r) => json<{ ok: boolean }>(r)),

  listSessions: () =>
    fetch("/api/sessions").then((r) =>
      json<{ sessions: Array<{ id: string; metadata: { title?: string }; updated_at: string }> }>(r),
    ),

  deleteSession: (id: string) =>
    fetch(`/api/sessions/${id}`, { method: "DELETE" }).then((r) =>
      json<{ ok: boolean }>(r),
    ),
};
