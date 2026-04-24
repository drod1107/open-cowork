import { useEffect, useState } from "react";
import { api } from "../lib/api";

type PermConfig = Record<string, Record<string, unknown>>;

export default function Permissions() {
  const [cfg, setCfg] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setCfg(await api.readConfig());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const save = async (next: Record<string, unknown>) => {
    setCfg(next);
    await api.writeConfig(next);
  };

  if (!cfg) return <div className="p-3 text-xs text-slate-500">loading…</div>;
  const perms = (cfg.permissions ?? {}) as PermConfig;

  const setDefault = (category: string, value: string) => {
    const next = {
      ...cfg,
      permissions: {
        ...perms,
        [category]: { ...(perms[category] ?? {}), default: value },
      },
    };
    void save(next);
  };

  const removeFromList = (category: string, list: string, item: string) => {
    const arr = ((perms[category]?.[list] as string[] | undefined) ?? []).filter(
      (x) => x !== item,
    );
    const next = {
      ...cfg,
      permissions: {
        ...perms,
        [category]: { ...(perms[category] ?? {}), [list]: arr },
      },
    };
    void save(next);
  };

  const addToList = (category: string, list: string, item: string) => {
    if (!item) return;
    const arr = ((perms[category]?.[list] as string[] | undefined) ?? []).concat(
      item,
    );
    const next = {
      ...cfg,
      permissions: {
        ...perms,
        [category]: { ...(perms[category] ?? {}), [list]: arr },
      },
    };
    void save(next);
  };

  return (
    <div className="p-3 space-y-3 text-xs" data-testid="permissions">
      <div className="font-semibold">Permissions</div>
      {error && <div className="text-red-400">{error}</div>}
      {Object.entries(perms).map(([cat, sub]) => (
        <CategoryBlock
          key={cat}
          name={cat}
          sub={sub as Record<string, unknown>}
          onDefault={(v) => setDefault(cat, v)}
          onRemove={(list, item) => removeFromList(cat, list, item)}
          onAdd={(list, item) => addToList(cat, list, item)}
        />
      ))}
    </div>
  );
}

function CategoryBlock({
  name,
  sub,
  onDefault,
  onRemove,
  onAdd,
}: {
  name: string;
  sub: Record<string, unknown>;
  onDefault: (v: string) => void;
  onRemove: (list: string, item: string) => void;
  onAdd: (list: string, item: string) => void;
}) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const listKeys = Object.keys(sub).filter(
    (k) => Array.isArray(sub[k]) && k !== "default",
  );

  return (
    <div className="border border-slate-800 rounded-md p-2 space-y-2">
      <div className="flex justify-between items-center">
        <span className="font-semibold">{name}</span>
        {typeof sub.default === "string" && (
          <select
            className="bg-slate-900 border border-slate-800 rounded-md px-2 py-1"
            value={sub.default}
            onChange={(e) => onDefault(e.target.value)}
            data-testid={`perm-default-${name}`}
          >
            <option value="ask">ask</option>
            <option value="allow">allow</option>
            <option value="deny">deny</option>
          </select>
        )}
      </div>
      {listKeys.map((list) => (
        <div key={list} className="space-y-1">
          <div className="text-slate-400">{list}</div>
          <div className="flex flex-wrap gap-1">
            {((sub[list] as string[]) || []).map((x) => (
              <button
                key={x}
                className="bg-slate-800 hover:bg-red-900/50 rounded-md px-2 py-0.5 font-mono"
                onClick={() => onRemove(list, x)}
                title="click to remove"
              >
                {x}
              </button>
            ))}
          </div>
          <div className="flex gap-1">
            <input
              className="flex-1 bg-slate-900 border border-slate-800 rounded-md px-2 py-1 font-mono"
              placeholder="pattern"
              value={draft[list] ?? ""}
              onChange={(e) =>
                setDraft((d) => ({ ...d, [list]: e.target.value }))
              }
            />
            <button
              className="bg-sky-600 hover:bg-sky-500 rounded-md px-2"
              onClick={() => {
                onAdd(list, draft[list] ?? "");
                setDraft((d) => ({ ...d, [list]: "" }));
              }}
            >
              add
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
