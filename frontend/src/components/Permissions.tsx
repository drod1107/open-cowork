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

type ProviderEntry = {
  type: string;
  base_url: string;
};

type Config = {
  provider?: string;
  base_url?: string;
  tools?: ToolConfig;
  permissions?: PermConfig;
  providers?: Record<string, ProviderEntry>;
  [key: string]: unknown;
};

const PROVIDER_DEFAULTS: Record<string, { type: string; base_url: string }> = {
  ollama: { type: "ollama", base_url: "http://localhost:11434" },
  "lm-studio": { type: "lmstudio", base_url: "http://localhost:1234" },
  vllm: { type: "vllm", base_url: "http://localhost:8000" },
  sglang: { type: "sglang", base_url: "http://localhost:30000" },
  nvidia: { type: "nvidia", base_url: "https://integrate.api.nvidia.com" },
  custom: { type: "openai-compat", base_url: "" },
};

const BUILTIN_PROVIDERS = new Set(["ollama", "lm-studio", "vllm", "sglang", "nvidia"]);

export default function Permissions() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAddProvider, setShowAddProvider] = useState(false);
  const [formType, setFormType] = useState("ollama");
  const [formNickname, setFormNickname] = useState("");
  const [formBaseUrl, setFormBaseUrl] = useState("");
  const [formApiKey, setFormApiKey] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [workingDir, setWorkingDir] = useState<string>("");
  const [editingWorkingDir, setEditingWorkingDir] = useState(false);
  const [workingDirInput, setWorkingDirInput] = useState("");
  const [workingDirError, setWorkingDirError] = useState<string | null>(null);

  const load = async () => {
    try {
      setCfg((await api.readConfig()) as Config);
      const wd = await api.getWorkingDir();
      setWorkingDir(wd.working_dir);
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

  const handleFormTypeChange = (t: string) => {
    setFormType(t);
    const defaults = PROVIDER_DEFAULTS[t];
    if (defaults) {
      setFormBaseUrl(defaults.base_url);
      if (t !== "custom" && !formNickname) {
        setFormNickname(t);
      }
    }
  };

  const openAddProvider = () => {
    setFormType("ollama");
    setFormNickname("ollama");
    setFormBaseUrl(PROVIDER_DEFAULTS.ollama.base_url);
    setFormApiKey("");
    setFormError(null);
    setShowAddProvider(true);
  };

  const submitAddProvider = async () => {
    if (!formNickname.trim()) {
      setFormError("Nickname is required");
      return;
    }
    if (!formBaseUrl.trim() && formType === "custom") {
      setFormError("Base URL is required");
      return;
    }
    const defaults = PROVIDER_DEFAULTS[formType];
    const providerType = defaults ? defaults.type : "openai-compat";
    const baseUrl = formBaseUrl.trim() || (defaults ? defaults.base_url : "");
    if (!baseUrl) {
      setFormError("Base URL is required");
      return;
    }
    try {
      await api.addProvider(formNickname.trim(), baseUrl, providerType);
      setShowAddProvider(false);
      await load();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    }
  };

  const deleteProvider = async (name: string) => {
    try {
      await api.deleteProvider(name);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const startEditWorkingDir = () => {
    setWorkingDirInput(workingDir);
    setWorkingDirError(null);
    setEditingWorkingDir(true);
  };

  const cancelEditWorkingDir = () => {
    setEditingWorkingDir(false);
    setWorkingDirError(null);
  };

  const saveWorkingDir = async () => {
    try {
      const result = await api.updateWorkingDir(workingDirInput.trim());
      setWorkingDir(result.working_dir);
      setEditingWorkingDir(false);
      setWorkingDirError(null);
    } catch (e) {
      setWorkingDirError(e instanceof Error ? e.message : String(e));
    }
  };

  if (!cfg) return <div className="p-3 text-xs text-slate-500">loading…</div>;

  const tools = (cfg.tools ?? {}) as ToolConfig;
  const perms = (cfg.permissions ?? {}) as PermConfig;
  const shellPerms = perms.shell ?? {};
  const providers = (cfg.providers ?? {}) as Record<string, ProviderEntry>;

  return (
    <div className="p-3 space-y-3 text-xs" data-testid="permissions">
      <div className="font-semibold">Settings</div>
      {error && <div className="text-red-400">{error}</div>}

      {/* Model Providers Section */}
      <div className="border border-slate-800 rounded-md p-2 space-y-2">
        <div className="flex justify-between items-center">
          <div className="font-semibold">Model Providers</div>
          <button
            className="bg-sky-700 hover:bg-sky-600 rounded-md px-2 py-0.5 text-xs"
            onClick={openAddProvider}
            data-testid="add-provider-btn"
          >
            +
          </button>
        </div>

        <div className="space-y-1">
          {Object.entries(providers).map(([name, entry]) => (
            <div
              key={name}
              className="flex justify-between items-center bg-slate-800/50 rounded-md px-2 py-1"
              data-testid={`provider-item-${name}`}
            >
              <div>
                <span className="font-mono">{name}</span>
                <span className="text-slate-500 ml-2">{entry.type}</span>
                <span className="text-slate-600 ml-2">{entry.base_url}</span>
              </div>
              <button
                className={`text-xs px-1 rounded ${
                  BUILTIN_PROVIDERS.has(name)
                    ? "text-slate-600 cursor-not-allowed"
                    : "text-red-400 hover:bg-red-900/30"
                }`}
                disabled={BUILTIN_PROVIDERS.has(name)}
                onClick={() => void deleteProvider(name)}
                data-testid={`delete-provider-${name}`}
                title={BUILTIN_PROVIDERS.has(name) ? "Cannot delete built-in provider" : "Delete provider"}
              >
                ×
              </button>
            </div>
          ))}
          {Object.keys(providers).length === 0 && (
            <div className="text-slate-500">No providers configured</div>
          )}
        </div>

        {/* Add Provider Popup Form */}
        {showAddProvider && (
          <div className="border border-sky-800 bg-slate-800 rounded-md p-2 space-y-2" data-testid="add-provider-form">
            <div className="font-semibold">Add Provider</div>
            {formError && <div className="text-red-400">{formError}</div>}

            <div className="space-y-1">
              <div className="text-slate-400">Provider Type</div>
              <select
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1 text-xs"
                value={formType}
                onChange={(e) => handleFormTypeChange(e.target.value)}
                data-testid="provider-type-select"
              >
                {Object.keys(PROVIDER_DEFAULTS).map((k) => (
                  <option key={k} value={k}>
                    {k === "custom" ? "Custom (OpenAI-compatible)" : k.charAt(0).toUpperCase() + k.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <div className="text-slate-400">Nickname</div>
              <input
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1 text-xs"
                value={formNickname}
                onChange={(e) => setFormNickname(e.target.value)}
                placeholder="my-provider"
                data-testid="provider-nickname-input"
              />
            </div>

            <div className="space-y-1">
              <div className="text-slate-400">Base URL</div>
              <input
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1 text-xs"
                value={formBaseUrl}
                onChange={(e) => setFormBaseUrl(e.target.value)}
                placeholder={formType === "custom" ? "https://api.example.com" : ""}
                data-testid="provider-baseurl-input"
              />
            </div>

            {(formType === "nvidia" || formType === "custom") && (
              <div className="space-y-1">
                <div className="text-slate-400">API Key (optional for Custom)</div>
                <input
                  className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1 text-xs"
                  type="password"
                  value={formApiKey}
                  onChange={(e) => setFormApiKey(e.target.value)}
                  placeholder={formType === "nvidia" ? "nvapi-..." : ""}
                  data-testid="provider-apikey-input"
                />
              </div>
            )}

            <div className="flex gap-2">
              <button
                className="bg-sky-700 hover:bg-sky-600 rounded-md px-3 py-1"
                onClick={() => void submitAddProvider()}
                data-testid="provider-save-btn"
              >
                Save
              </button>
              <button
                className="bg-slate-700 hover:bg-slate-600 rounded-md px-3 py-1"
                onClick={() => setShowAddProvider(false)}
                data-testid="provider-cancel-btn"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Working Directory Section */}
  <div className="border border-slate-800 rounded-md p-2 space-y-2">
    <div className="font-semibold">Working Directory</div>
    {!editingWorkingDir ? (
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs flex-1 break-all" data-testid="working-dir-display">{workingDir}</span>
        <button
          className="bg-sky-700 hover:bg-sky-600 rounded-md px-2 py-0.5 text-xs"
          onClick={startEditWorkingDir}
          data-testid="working-dir-edit-btn"
        >
          Edit
        </button>
      </div>
    ) : (
      <div className="space-y-2">
        <input
          className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1 text-xs font-mono"
          value={workingDirInput}
          onChange={(e) => setWorkingDirInput(e.target.value)}
          data-testid="working-dir-input"
        />
        {workingDirError && <div className="text-red-400 text-xs" data-testid="working-dir-error">{workingDirError}</div>}
        <div className="flex gap-2">
          <button
            className="bg-sky-700 hover:bg-sky-600 rounded-md px-3 py-1 text-xs"
            onClick={() => void saveWorkingDir()}
            data-testid="working-dir-save-btn"
          >
            Save
          </button>
          <button
            className="bg-slate-700 hover:bg-slate-600 rounded-md px-3 py-1 text-xs"
            onClick={cancelEditWorkingDir}
            data-testid="working-dir-cancel-btn"
          >
            Cancel
          </button>
        </div>
      </div>
    )}
  </div>

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
