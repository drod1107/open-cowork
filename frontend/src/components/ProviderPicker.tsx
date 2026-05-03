import { useEffect, useRef, useState } from "react";
import { api, type ProviderDef } from "../lib/api";

// ── Reachability dot ──────────────────────────────────────────────────────────
function ReachDot({ reachable, checking }: { reachable: boolean | null; checking: boolean }) {
  if (checking) return <span className="inline-block w-2 h-2 rounded-full bg-slate-500 animate-pulse" />;
  if (reachable === true) return <span className="inline-block w-2 h-2 rounded-full bg-emerald-400" title="Reachable" />;
  if (reachable === false) return <span className="inline-block w-2 h-2 rounded-full bg-slate-600" title="Not reachable" />;
  return <span className="inline-block w-2 h-2 rounded-full bg-slate-700" title="Not checked" />;
}

// ── Single provider row ───────────────────────────────────────────────────────
function ProviderRow({
  provider,
  reachable,
  checking,
  onActivate,
  onSave,
  onPing,
}: {
  provider: ProviderDef;
  reachable: boolean | null;
  checking: boolean;
  onActivate: () => void;
  onSave: (base_url: string, api_key: string | null) => void;
  onPing: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [baseUrl, setBaseUrl] = useState(provider.base_url || provider.default_base_url);
  // Don't pre-fill with the masked key — keep blank so user types a real new value
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  // Keep local fields in sync if parent refreshes
  useEffect(() => {
    setBaseUrl(provider.base_url || provider.default_base_url);
    setApiKey(""); // always blank — user enters new key if they want to change it
  }, [provider.base_url, provider.default_base_url]);

  const canActivate = reachable === true;
  const isActive = provider.active;

  const handleSave = async () => {
    setSaving(true);
    try {
      // Only send api_key if the user actually typed a new one
      await onSave(baseUrl, apiKey.trim() || null as unknown as string);
      setApiKey(""); // clear field after save
      onPing(); // re-ping after saving
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`border-b border-slate-700/40 ${isActive ? "bg-slate-800/60" : ""}`}>
      {/* Main row */}
      <div className="flex items-center gap-2 px-3 py-2">
        <ReachDot reachable={reachable} checking={checking} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className={`text-xs font-semibold ${canActivate || !provider.local ? "text-slate-200" : "text-slate-500"}`}>
              {provider.name}
            </span>
            {isActive && (
              <span className="text-xs bg-sky-700 text-sky-100 px-1.5 rounded-full">active</span>
            )}
            {!provider.local && (
              <span className="text-xs text-slate-600">cloud</span>
            )}
          </div>
          <div className="text-xs text-slate-600 truncate">{provider.description}</div>
        </div>
        <div className="flex gap-1 shrink-0">
          <button
            onClick={() => { setExpanded((v) => !v); }}
            className="text-xs text-slate-500 hover:text-slate-300 px-1"
            title="Edit configuration"
          >
            {expanded ? "▲" : "▼"}
          </button>
          {!isActive && (
            <button
              onClick={onActivate}
              disabled={!canActivate}
              className="text-xs bg-sky-800 hover:bg-sky-700 disabled:bg-slate-700 disabled:text-slate-500 text-sky-100 px-2 py-0.5 rounded"
              title={canActivate ? "Switch to this provider" : "Provider not reachable — check URL and start the server"}
            >
              Use
            </button>
          )}
        </div>
      </div>

      {/* Expanded config */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 bg-slate-900/40">
          <label className="block">
            <span className="text-xs text-slate-500">Base URL</span>
            <input
              className="mt-0.5 w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-100 font-mono outline-none focus:border-sky-600"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={provider.default_base_url}
            />
          </label>
          {provider.auth_type === "bearer" && (
            <label className="block">
              <span className="text-xs text-slate-500">
                API Key
                {provider.has_key
                  ? <span className="ml-1.5 text-emerald-500">✓ key set</span>
                  : <span className="ml-1.5 text-amber-500">not set</span>}
              </span>
              <input
                type="password"
                className="mt-0.5 w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-100 font-mono outline-none focus:border-sky-600"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={provider.has_key ? "Enter new key to replace…" : "sk-…"}
              />
            </label>
          )}
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-xs bg-sky-700 hover:bg-sky-600 text-white px-2 py-1 rounded disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={onPing}
              disabled={checking}
              className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 px-2 py-1 rounded disabled:opacity-50"
            >
              {checking ? "Pinging…" : "Ping"}
            </button>
            {provider.slug === "opencode-zen" && (
              <a
                href="https://opencode.ai/zen"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-sky-400 hover:text-sky-300 px-1 py-1"
              >
                Get free key ↗
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main ProviderPicker ───────────────────────────────────────────────────────
export default function ProviderPicker({ onProviderChange }: { onProviderChange?: () => void }) {
  const [open, setOpen] = useState(false);
  const [providers, setProviders] = useState<ProviderDef[]>([]);
  const [reachability, setReachability] = useState<Record<string, boolean | null>>({});
  const [checking, setChecking] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const activeProvider = providers.find((p) => p.active);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.listProviders();
      setProviders(r.providers);
      // Start pinging all providers concurrently
      pingAll(r.providers);
    } finally {
      setLoading(false);
    }
  };

  const pingAll = (list: ProviderDef[]) => {
    list.forEach((p) => pingOne(p.slug));
  };

  const pingOne = async (slug: string) => {
    setChecking((prev) => ({ ...prev, [slug]: true }));
    try {
      const r = await api.pingProvider(slug);
      setReachability((prev) => ({ ...prev, [slug]: r.reachable }));
    } catch {
      setReachability((prev) => ({ ...prev, [slug]: false }));
    } finally {
      setChecking((prev) => ({ ...prev, [slug]: false }));
    }
  };

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleOpen = () => {
    setOpen((v) => {
      if (!v) load();
      return !v;
    });
  };

  const handleActivate = async (slug: string) => {
    await api.updateProvider(slug, { activate: true });
    await load();
    onProviderChange?.();
    setOpen(false);
  };

  const handleSave = async (slug: string, base_url: string, api_key: string | null) => {
    const patch: { base_url?: string; api_key?: string } = { base_url };
    if (api_key) patch.api_key = api_key;
    await api.updateProvider(slug, patch);
    await load();
  };

  // Dot color for the header button
  const activeReachable = activeProvider ? reachability[activeProvider.slug] : null;

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={handleOpen}
        className="flex items-center gap-1.5 text-xs text-slate-300 hover:text-slate-100 bg-slate-800 hover:bg-slate-700 px-2 py-1 rounded-md"
        data-testid="provider-picker-btn"
        title="Switch provider"
      >
        <ReachDot reachable={activeReachable} checking={!!activeProvider && !!checking[activeProvider.slug]} />
        <span>{loading ? "…" : (activeProvider?.name ?? "provider")}</span>
        <span className="text-slate-500 text-xs">▾</span>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 w-80 bg-slate-900 border border-slate-700 rounded-lg shadow-xl overflow-hidden">
          <div className="px-3 py-2 border-b border-slate-700 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Providers</span>
            <button
              onClick={() => pingAll(providers)}
              className="text-xs text-slate-500 hover:text-slate-300"
              title="Re-ping all"
            >↻ ping all</button>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {providers.map((p) => (
              <ProviderRow
                key={p.slug}
                provider={p}
                reachable={reachability[p.slug] ?? null}
                checking={!!checking[p.slug]}
                onActivate={() => handleActivate(p.slug)}
                onSave={(bu, ak) => handleSave(p.slug, bu, ak)}
                onPing={() => pingOne(p.slug)}
              />
            ))}
          </div>
          <div className="px-3 py-1.5 border-t border-slate-700 text-xs text-slate-600">
            Green dot = server responding · Use = switch active provider
          </div>
        </div>
      )}
    </div>
  );
}
