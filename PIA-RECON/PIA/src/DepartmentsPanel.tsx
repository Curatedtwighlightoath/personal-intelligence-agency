import { useEffect, useState } from "react";

// Standalone-ish panel for editing per-department LLM config. Intentionally
// low-polish — the user's only near-term goal here is being able to swap
// providers for testing.

interface DeptConfig {
  department: string;
  provider: string;
  model: string;
  api_key_ref: string | null;
  base_url: string | null;
  extra: Record<string, any>;
  updated_at: string | null;
}

const PROVIDERS = ["anthropic", "openai", "ollama"];

async function fetchJSON(path: string, init?: RequestInit) {
  const r = await fetch(path, init);
  if (!r.ok) throw new Error(`${init?.method || "GET"} ${path}: ${r.status}`);
  return r.json();
}

function DepartmentCard({ cfg, onSaved }: { cfg: DeptConfig; onSaved: () => void }) {
  const [provider, setProvider]     = useState(cfg.provider);
  const [model, setModel]           = useState(cfg.model);
  const [apiKeyRef, setApiKeyRef]   = useState(cfg.api_key_ref || "");
  const [baseUrl, setBaseUrl]       = useState(cfg.base_url || "");
  const [busy, setBusy]             = useState(false);
  const [msg, setMsg]               = useState<string | null>(null);

  async function save() {
    setBusy(true); setMsg(null);
    try {
      await fetchJSON(`/api/departments/${cfg.department}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider, model,
          api_key_ref: apiKeyRef || null,
          base_url:    baseUrl || null,
          extra:       cfg.extra,
        }),
      });
      setMsg("saved");
      onSaved();
    } catch (e: any) {
      setMsg(`error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true); setMsg("testing...");
    try {
      const r = await fetchJSON(`/api/departments/${cfg.department}/test`, { method: "POST" });
      if (r.ok) {
        setMsg(`ok (${r.latency_ms} ms)`);
      } else {
        setMsg(`failed: ${r.error}`);
      }
    } catch (e: any) {
      setMsg(`error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  const field: React.CSSProperties = {
    width: "100%", background: "#262626", border: "none",
    borderBottom: "0.0625rem solid #484847", padding: "0.5rem 0.75rem",
    color: "#e8e8e8", fontFamily: "'JetBrains Mono', monospace",
    fontSize: "0.75rem", outline: "none", marginBottom: "0.5rem",
  };
  const label: React.CSSProperties = {
    display: "block", fontSize: "0.625rem", letterSpacing: "0.15em",
    textTransform: "uppercase", color: "#767575", marginBottom: "0.25rem",
    fontFamily: "'Space Grotesk', sans-serif",
  };
  const btn: React.CSSProperties = {
    background: "#85adff", color: "#000", border: "none",
    padding: "0.5rem 1rem", fontFamily: "'Space Grotesk', sans-serif",
    fontSize: "0.6875rem", letterSpacing: "0.1em",
    textTransform: "uppercase", fontWeight: 700, cursor: "pointer",
    marginRight: "0.5rem",
  };

  return (
    <div style={{ background: "#131313", padding: "1.25rem", marginBottom: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase", color: "#e8e8e8" }}>
          {cfg.department}
        </div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.6875rem", color: "#767575" }}>
          updated {cfg.updated_at || "never"}
        </div>
      </div>

      <label style={label}>Provider</label>
      <select value={provider} onChange={e => setProvider(e.target.value)} style={field}>
        {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
      </select>

      <label style={label}>Model</label>
      <input value={model} onChange={e => setModel(e.target.value)} style={field}
             placeholder="e.g. claude-sonnet-4-20250514 or gpt-4o-mini" />

      <label style={label}>API Key Env Var Name</label>
      <input value={apiKeyRef} onChange={e => setApiKeyRef(e.target.value)} style={field}
             placeholder="ANTHROPIC_API_KEY — the NAME, not the secret" />

      <label style={label}>Base URL (optional — e.g. Ollama)</label>
      <input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} style={field}
             placeholder="http://localhost:11434/v1" />

      <div style={{ marginTop: "0.75rem" }}>
        <button style={btn} onClick={save} disabled={busy}>Save</button>
        <button style={{ ...btn, background: "#59ee50" }} onClick={test} disabled={busy}>Test</button>
        {msg && (
          <span style={{ marginLeft: "0.75rem", fontFamily: "'JetBrains Mono', monospace",
                         fontSize: "0.75rem", color: msg.startsWith("error") || msg.startsWith("failed") ? "#ff716c" : "#59ee50" }}>
            {msg}
          </span>
        )}
      </div>
    </div>
  );
}

export default function DepartmentsPanel() {
  const [configs, setConfigs] = useState<DeptConfig[]>([]);
  const [err, setErr]         = useState<string | null>(null);

  async function load() {
    try {
      const data = await fetchJSON("/api/departments");
      setConfigs(data);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div style={{ padding: "1.5rem", maxWidth: "40rem" }}>
      <div style={{ marginBottom: "1rem", fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "1.25rem", fontWeight: 900, letterSpacing: "-0.02em", color: "#e8e8e8" }}>
        Departments
      </div>
      <div style={{ marginBottom: "1.5rem", fontSize: "0.8125rem", color: "#767575",
                    fontFamily: "'Inter', sans-serif" }}>
        Per-department LLM provider, model, and API-key env-var name. Secrets are never stored or sent —
        only the NAME of the environment variable the backend should read.
      </div>
      {err && <div style={{ color: "#ff716c", marginBottom: "1rem" }}>Failed to load: {err}</div>}
      {configs.map(c => <DepartmentCard key={c.department} cfg={c} onSaved={load} />)}
    </div>
  );
}
