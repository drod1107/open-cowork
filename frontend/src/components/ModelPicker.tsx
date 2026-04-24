import { useEffect, useState } from "react";
import { api, type Model } from "../lib/api";

export default function ModelPicker() {
  const [models, setModels] = useState<Model[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [provider, setProvider] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.listModels(force);
      setModels(r.models);
      setSelected(r.selected);
      setProvider(r.provider);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const choose = async (id: string) => {
    await api.selectModel(id);
    setSelected(id);
  };

  return (
    <div className="flex items-center gap-2" data-testid="model-picker">
      <span className="text-xs text-slate-400">{provider || "…"}</span>
      <select
        className="bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-sm"
        value={selected ?? ""}
        onChange={(e) => void choose(e.target.value)}
        data-testid="model-select"
      >
        <option value="" disabled>
          {loading ? "loading…" : "select a model"}
        </option>
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.id}
            {m.supports_vision ? " 👁" : ""}
          </option>
        ))}
      </select>
      <button
        className="text-xs bg-slate-800 hover:bg-slate-700 rounded-md px-2 py-1"
        onClick={() => void load(true)}
        data-testid="refresh-models"
      >
        ↻
      </button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}
