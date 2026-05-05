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
      json<{ deleted: boolean }>(r),
    ),

  getSession: (id: string) =>
    fetch(`/api/sessions/${id}`).then((r) =>
      json<{ id: string; messages: Array<{ role: string; content: string }>; metadata: { title?: string }; created_at: string; updated_at: string }>(r),
    ),

  addProvider: (nickname: string, base_url: string, provider_type: string) =>
    fetch("/api/providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nickname, base_url, provider_type }),
    }).then((r) => {
      if (!r.ok) return r.json().then((e) => { throw new Error(e.detail || `${r.status}`); });
      return json<{ ok: boolean }>(r);
    }),

  deleteProvider: (name: string) =>
    fetch(`/api/providers/${encodeURIComponent(name)}`, { method: "DELETE" }).then((r) => {
      if (!r.ok) return r.json().then((e) => { throw new Error(e.detail || `${r.status}`); });
      return json<{ ok: boolean }>(r);
    }),

  getWorkingDir: () =>
    fetch("/api/config/working_dir").then((r) =>
      json<{ working_dir: string }>(r),
    ),

  updateWorkingDir: (working_dir: string) =>
    fetch("/api/config/working_dir", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ working_dir }),
    }).then((r) => {
      if (!r.ok) return r.json().then((e) => { throw new Error(e.detail || `${r.status}`); });
      return json<{ working_dir: string }>(r);
    }),

  listSkills: () =>
    fetch("/api/skills").then((r) =>
      json<{ skills: Array<{ name: string; description: string }> }>(r),
    ),

  useSkill: (sessionId: string, skillName: string) =>
    fetch(`/api/sessions/${sessionId}/use-skill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill_name: skillName }),
    }).then((r) => {
      if (!r.ok) return r.json().then((e) => { throw new Error(e.detail || `${r.status}`); });
      return json<{ activated: string }>(r);
    }),
};
