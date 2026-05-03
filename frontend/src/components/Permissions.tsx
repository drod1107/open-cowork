import { useEffect, useState } from "react";
import { api } from "../lib/api";

type ToolConfig = {
  shell?: boolean;
};

type PermConfig = {
  shell?: {
    allowed_commands?: string[];
    blocked_commands?: string[];
  };
};

type Config = {
  provider?: string;
  base_url?: string;
  tools?: ToolConfig;
  permissions?: PermConfig;
  [key: string]: unknown;
};

export default function Permissions() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setCfg(await api.readConfig() as Config);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const save = async (next: Config) => {
    setCfg(next);
    await api.writeConfig(next);
  };

  if (!cfg) return <div className="p-3 text-xs text-slate-500">loading…</div>;

  const tools = (cfg.tools ?? {}) as ToolConfig;
  const perms = (cfg.permissions ?? {}) as PermConfig;
  const shellPerms = perms.shell ?? {};

  return (
    <div className="p-3 space-y-3 text-xs" data-testid="permissions">
      <div className="font-semibold">Settings</div>
      {error && <div className="text-red-400">{error}</div>}

      {/* Tools Section */}
      <div className="border border-slate-800 rounded-md p-2 space-y-2">
        <div className="font-semibold">Tools</div>
        <div className="flex justify-between items-center">
          <span>Shell/Bash Tool</span>
          <button
            role="switch"
            aria-checked={tools.shell !== false}
            onClick={() =>
              save({ ...cfg, tools: { ...tools, shell: tools.shell === false } })
            }
            data-testid="tool-shell-toggle"
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              tools.shell !== false ? "bg-sky-600" : "bg-slate-700"
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                tools.shell !== false ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
          <span className="ml-2">{tools.shell !== false ? "Enabled" : "Disabled"}</span>
        </div>
      </div>

      {/* Permissions Section - Shell only for MVP */}
      <div className="border border-slate-800 rounded-md p-2 space-y-2">
        <div className="font-semibold">Permissions (Shell)</div>

        {/* Allowed commands */}
        <div className="space-y-1">
          <div className="text-slate-400">Allowed Commands</div>
          <div className="flex flex-wrap gap-1">
            {(shellPerms.allowed_commands ?? []).map((cmd: string) => (
              <button
                key={cmd}
                className="bg-slate-800 hover:bg-red-900/50 rounded-md px-2 py-0.5 font-mono text-xs"
                onClick={() =>
                  save({
                    ...cfg,
                    permissions: {
                      ...perms,
                      shell: {
                        ...shellPerms,
                        allowed_commands: (shellPerms.allowed_commands ?? []).filter(
                          (c: string) => c !== cmd
                        ),
                      },
                    },
                  })
                }
                title="click to remove"
              >
                {cmd}
              </button>
            ))}
          </div>
        </div>

        {/* Blocked commands */}
        <div className="space-y-1">
          <div className="text-slate-400">Blocked Commands</div>
          <div className="flex flex-wrap gap-1">
            {(shellPerms.blocked_commands ?? []).map((cmd: string) => (
              <button
                key={cmd}
                className="bg-slate-800 hover:bg-emerald-900/50 rounded-md px-2 py-0.5 font-mono text-xs"
                onClick={() =>
                  save({
                    ...cfg,
                    permissions: {
                      ...perms,
                      shell: {
                        ...shellPerms,
                        blocked_commands: (shellPerms.blocked_commands ?? []).filter(
                          (c: string) => c !== cmd
                        ),
                      },
                    },
                  })
                }
                title="click to remove from blocked list"
              >
                {cmd}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
