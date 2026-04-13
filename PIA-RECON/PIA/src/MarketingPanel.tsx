import { useEffect, useState } from "react";

// Marketing department panel: edit singleton product profile, generate
// social-post drafts across Twitter/X, LinkedIn, Instagram, TikTok scripts,
// and triage the persisted draft list. Intentionally utilitarian — the
// visual language matches DepartmentsPanel, not the dashboard cards.

interface PlatformSpec {
  id: string;
  label: string;
  char_limit: number | null;
  format_rules: string;
}

interface Product {
  id: string;
  name: string;
  one_liner: string;
  audience: string;
  tone: string;
  key_messages: string[];
  links: { label: string; url: string }[];
  updated_at: string | null;
}

interface Draft {
  id: string;
  platform: string;
  topic: string;
  content: string;
  rationale: string | null;
  variant_index: number;
  status: string;
  rating: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

const STATUSES = ["draft", "approved", "rejected", "posted"] as const;

async function fetchJSON(path: string, init?: RequestInit) {
  const r = await fetch(path, init);
  if (!r.ok) {
    const body = await r.text().catch(() => "");
    throw new Error(`${init?.method || "GET"} ${path}: ${r.status} ${body}`);
  }
  return r.json();
}

// ── Shared styles (mirrors DepartmentsPanel tokens) ─────────────────────────

const field: React.CSSProperties = {
  width: "100%", background: "#262626", border: "none",
  borderBottom: "0.0625rem solid #484847", padding: "0.5rem 0.75rem",
  color: "#e8e8e8", fontFamily: "'JetBrains Mono', monospace",
  fontSize: "0.75rem", outline: "none", marginBottom: "0.5rem",
  boxSizing: "border-box",
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
const btnAlt: React.CSSProperties = { ...btn, background: "#59ee50" };
const btnGhost: React.CSSProperties = {
  ...btn, background: "transparent", color: "#e8e8e8",
  border: "0.0625rem solid #484847",
};
const card: React.CSSProperties = {
  background: "#131313", padding: "1.25rem", marginBottom: "1rem",
};

// ── Product editor ──────────────────────────────────────────────────────────

function ProductCard({ product, onSaved }: { product: Product; onSaved: (p: Product) => void }) {
  const [name, setName]           = useState(product.name);
  const [oneLiner, setOneLiner]   = useState(product.one_liner || "");
  const [audience, setAudience]   = useState(product.audience || "");
  const [tone, setTone]           = useState(product.tone || "");
  const [keyMsgs, setKeyMsgs]     = useState((product.key_messages || []).join("\n"));
  const [linksText, setLinksText] = useState(
    (product.links || []).map(l => `${l.label}|${l.url}`).join("\n")
  );
  const [busy, setBusy] = useState(false);
  const [msg,  setMsg]  = useState<string | null>(null);

  async function save() {
    setBusy(true); setMsg(null);
    try {
      const links = linksText.split("\n").map(s => s.trim()).filter(Boolean).map(line => {
        const [lbl, ...rest] = line.split("|");
        return { label: (lbl || "").trim(), url: rest.join("|").trim() };
      }).filter(l => l.url);
      const key_messages = keyMsgs.split("\n").map(s => s.trim()).filter(Boolean);
      const saved = await fetchJSON("/api/marketing/product", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, one_liner: oneLiner, audience, tone, key_messages, links }),
      });
      setMsg("saved");
      onSaved(saved);
    } catch (e: any) {
      setMsg(`error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700,
                      letterSpacing: "0.05em", textTransform: "uppercase", color: "#e8e8e8" }}>
          Product
        </div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace",
                      fontSize: "0.6875rem", color: "#767575" }}>
          updated {product.updated_at || "never"}
        </div>
      </div>

      <label style={label}>Name</label>
      <input value={name} onChange={e => setName(e.target.value)} style={field} />

      <label style={label}>One-liner</label>
      <input value={oneLiner} onChange={e => setOneLiner(e.target.value)} style={field}
             placeholder="What it is, in one sentence" />

      <label style={label}>Audience</label>
      <input value={audience} onChange={e => setAudience(e.target.value)} style={field}
             placeholder="Who it's for" />

      <label style={label}>Tone</label>
      <input value={tone} onChange={e => setTone(e.target.value)} style={field}
             placeholder="e.g. direct, technical, zero hype" />

      <label style={label}>Key messages (one per line)</label>
      <textarea value={keyMsgs} onChange={e => setKeyMsgs(e.target.value)}
                style={{ ...field, minHeight: "5rem", resize: "vertical" }}
                placeholder={"vendor-neutral\nSQLite-simple\nruns on your machine"} />

      <label style={label}>Links (one per line, format: Label|https://url)</label>
      <textarea value={linksText} onChange={e => setLinksText(e.target.value)}
                style={{ ...field, minHeight: "3.5rem", resize: "vertical" }}
                placeholder={"Docs|https://example.com/docs\nGitHub|https://github.com/you/repo"} />

      <div style={{ marginTop: "0.75rem" }}>
        <button style={btn} onClick={save} disabled={busy}>Save Product</button>
        {msg && (
          <span style={{ marginLeft: "0.75rem", fontFamily: "'JetBrains Mono', monospace",
                         fontSize: "0.75rem",
                         color: msg.startsWith("error") ? "#ff716c" : "#59ee50" }}>
            {msg}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Draft generator ─────────────────────────────────────────────────────────

function Generator({ platforms, onGenerated }: {
  platforms: PlatformSpec[];
  onGenerated: (drafts: Draft[]) => void;
}) {
  const [platform, setPlatform] = useState(platforms[0]?.id || "twitter");
  const [topic, setTopic]       = useState("");
  const [variants, setVariants] = useState(3);
  const [busy, setBusy]         = useState(false);
  const [msg,  setMsg]          = useState<string | null>(null);

  async function generate() {
    if (!topic.trim()) { setMsg("error: topic required"); return; }
    setBusy(true); setMsg("generating...");
    try {
      const drafts = await fetchJSON("/api/marketing/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform, topic, variants }),
      });
      setMsg(`generated ${drafts.length}`);
      onGenerated(drafts);
      setTopic("");
    } catch (e: any) {
      setMsg(`error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={card}>
      <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700,
                    letterSpacing: "0.05em", textTransform: "uppercase", color: "#e8e8e8",
                    marginBottom: "1rem" }}>
        Draft New Posts
      </div>

      <label style={label}>Platform</label>
      <select value={platform} onChange={e => setPlatform(e.target.value)} style={field}>
        {platforms.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
      </select>

      <label style={label}>Topic / angle</label>
      <input value={topic} onChange={e => setTopic(e.target.value)} style={field}
             placeholder="launch announcement, feature teaser, lessons learned…" />

      <label style={label}>Variants (1-5)</label>
      <input type="number" min={1} max={5}
             value={variants}
             onChange={e => setVariants(Math.max(1, Math.min(5, Number(e.target.value) || 1)))}
             style={field} />

      <div style={{ marginTop: "0.75rem" }}>
        <button style={btnAlt} onClick={generate} disabled={busy}>
          {busy ? "Generating..." : "Generate"}
        </button>
        {msg && (
          <span style={{ marginLeft: "0.75rem", fontFamily: "'JetBrains Mono', monospace",
                         fontSize: "0.75rem",
                         color: msg.startsWith("error") ? "#ff716c" : "#59ee50" }}>
            {msg}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Draft row ───────────────────────────────────────────────────────────────

function DraftCard({ draft, platforms, onChanged, onDeleted }: {
  draft: Draft;
  platforms: PlatformSpec[];
  onChanged: (d: Draft) => void;
  onDeleted: (id: string) => void;
}) {
  const [content, setContent] = useState(draft.content);
  const [notes, setNotes]     = useState(draft.notes || "");
  const [busy, setBusy]       = useState(false);
  const [msg,  setMsg]        = useState<string | null>(null);

  const spec = platforms.find(p => p.id === draft.platform);
  const limit = spec?.char_limit ?? null;
  const over = limit !== null && content.length > limit;

  async function patch(body: any) {
    setBusy(true); setMsg(null);
    try {
      const updated = await fetchJSON(`/api/marketing/drafts/${draft.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      onChanged(updated);
      setMsg("saved");
    } catch (e: any) {
      setMsg(`error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function del() {
    if (!confirm("Delete this draft?")) return;
    setBusy(true);
    try {
      await fetchJSON(`/api/marketing/drafts/${draft.id}`, { method: "DELETE" });
      onDeleted(draft.id);
    } catch (e: any) {
      setMsg(`error: ${e.message}`);
      setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setMsg("copied");
    } catch {
      setMsg("error: clipboard unavailable");
    }
  }

  const statusColor: Record<string, string> = {
    draft: "#767575", approved: "#59ee50", rejected: "#ff716c", posted: "#85adff",
  };

  return (
    <div style={{ ...card, borderLeft: `0.125rem solid ${statusColor[draft.status] || "#484847"}` }}>
      <div style={{ display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginBottom: "0.5rem" }}>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.6875rem",
                      color: "#767575" }}>
          {(spec?.label || draft.platform).toUpperCase()} · variant {draft.variant_index + 1}
          {" · "}topic: {draft.topic}
        </div>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "0.625rem",
                      textTransform: "uppercase", letterSpacing: "0.15em",
                      color: statusColor[draft.status] || "#e8e8e8" }}>
          {draft.status}
        </div>
      </div>

      <textarea value={content} onChange={e => setContent(e.target.value)}
                style={{ ...field, minHeight: "6rem", resize: "vertical",
                         fontSize: "0.8125rem", lineHeight: 1.5 }} />

      <div style={{ display: "flex", justifyContent: "space-between",
                    fontFamily: "'JetBrains Mono', monospace", fontSize: "0.6875rem",
                    color: over ? "#ff716c" : "#767575", marginBottom: "0.75rem" }}>
        <span>{content.length}{limit !== null ? ` / ${limit}` : ""} chars</span>
        {draft.rationale && <span title={draft.rationale} style={{ maxWidth: "60%",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          why: {draft.rationale}
        </span>}
      </div>

      <label style={label}>Notes</label>
      <input value={notes} onChange={e => setNotes(e.target.value)} style={field}
             placeholder="scratchpad" />

      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem",
                    alignItems: "center", marginTop: "0.5rem" }}>
        <button style={btn} onClick={() => patch({ content, notes })} disabled={busy}>Save</button>
        {STATUSES.map(s => (
          <button key={s}
                  style={{ ...btnGhost,
                    color: draft.status === s ? "#000" : "#e8e8e8",
                    background: draft.status === s ? (statusColor[s] || "#85adff") : "transparent" }}
                  onClick={() => patch({ status: s })} disabled={busy}>
            {s}
          </button>
        ))}
        <button style={btnGhost} onClick={copy} disabled={busy}>Copy</button>
        <button style={{ ...btnGhost, borderColor: "#ff716c", color: "#ff716c" }}
                onClick={del} disabled={busy}>Delete</button>
        <div style={{ marginLeft: "0.5rem", display: "flex", gap: "0.125rem" }}>
          {[1,2,3,4,5].map(n => (
            <span key={n} onClick={() => !busy && patch({ rating: n })}
                  style={{ cursor: busy ? "default" : "pointer",
                           color: (draft.rating || 0) >= n ? "#ffb86c" : "#484847",
                           fontFamily: "'JetBrains Mono', monospace", fontSize: "1rem" }}>
              ★
            </span>
          ))}
        </div>
        {msg && (
          <span style={{ marginLeft: "0.5rem", fontFamily: "'JetBrains Mono', monospace",
                         fontSize: "0.75rem",
                         color: msg.startsWith("error") ? "#ff716c" : "#59ee50" }}>
            {msg}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Top-level panel ─────────────────────────────────────────────────────────

export default function MarketingPanel() {
  const [platforms, setPlatforms] = useState<PlatformSpec[]>([]);
  const [product, setProduct]     = useState<Product | null>(null);
  const [drafts, setDrafts]       = useState<Draft[]>([]);
  const [filterPlatform, setFilterPlatform] = useState<string>("");
  const [filterStatus, setFilterStatus]     = useState<string>("");
  const [err, setErr]             = useState<string | null>(null);

  async function loadAll() {
    try {
      const [p, prod] = await Promise.all([
        fetchJSON("/api/marketing/platforms"),
        fetchJSON("/api/marketing/product").catch(() => null),
      ]);
      setPlatforms(p);
      setProduct(prod);
      await loadDrafts();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function loadDrafts() {
    const qs = new URLSearchParams();
    if (filterPlatform) qs.set("platform", filterPlatform);
    if (filterStatus)   qs.set("status",   filterStatus);
    qs.set("limit", "100");
    try {
      const data = await fetchJSON(`/api/marketing/drafts?${qs.toString()}`);
      setDrafts(data);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => { loadAll(); }, []);
  useEffect(() => { loadDrafts(); }, [filterPlatform, filterStatus]);

  function handleGenerated(newDrafts: Draft[]) {
    setDrafts(prev => [...newDrafts, ...prev]);
  }
  function handleChanged(d: Draft) {
    setDrafts(prev => prev.map(x => x.id === d.id ? d : x));
  }
  function handleDeleted(id: string) {
    setDrafts(prev => prev.filter(x => x.id !== id));
  }

  return (
    <div style={{ padding: "1.5rem", maxWidth: "50rem" }}>
      <div style={{ marginBottom: "1rem", fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "1.25rem", fontWeight: 900, letterSpacing: "-0.02em",
                    color: "#e8e8e8" }}>
        Marketing
      </div>
      <div style={{ marginBottom: "1.5rem", fontSize: "0.8125rem", color: "#767575",
                    fontFamily: "'Inter', sans-serif" }}>
        Define your product once, then draft social-post variants across Twitter/X,
        LinkedIn, Instagram and TikTok/Reels. Drafts stay local in SQLite — nothing
        posts automatically.
      </div>

      {err && <div style={{ color: "#ff716c", marginBottom: "1rem" }}>Failed to load: {err}</div>}

      {product && <ProductCard product={product} onSaved={setProduct} />}
      {platforms.length > 0 && <Generator platforms={platforms} onGenerated={handleGenerated} />}

      <div style={{ ...card, display: "flex", gap: "0.75rem", alignItems: "center",
                    marginBottom: "0.5rem" }}>
        <span style={{ ...label, margin: 0 }}>Filter:</span>
        <select value={filterPlatform} onChange={e => setFilterPlatform(e.target.value)}
                style={{ ...field, marginBottom: 0, width: "auto" }}>
          <option value="">all platforms</option>
          {platforms.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
                style={{ ...field, marginBottom: 0, width: "auto" }}>
          <option value="">all statuses</option>
          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <span style={{ marginLeft: "auto", fontFamily: "'JetBrains Mono', monospace",
                       fontSize: "0.6875rem", color: "#767575" }}>
          {drafts.length} draft{drafts.length === 1 ? "" : "s"}
        </span>
      </div>

      {drafts.length === 0 && (
        <div style={{ ...card, color: "#767575", fontFamily: "'Inter', sans-serif",
                      fontSize: "0.8125rem" }}>
          No drafts yet. Generate some above.
        </div>
      )}
      {drafts.map(d => (
        <DraftCard key={d.id} draft={d} platforms={platforms}
                   onChanged={handleChanged} onDeleted={handleDeleted} />
      ))}
    </div>
  );
}
