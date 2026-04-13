import { useState, useEffect, useCallback } from "react";
import DepartmentsPanel from "./DepartmentsPanel";
import MarketingPanel from "./MarketingPanel";

// ── Design Tokens ──────────────────────────────────────────────────────────
const T = {
  bg: "#0e0e0e", surface: "#0e0e0e", sContainerLowest: "#000000",
  sContainer: "#1a1a1a", sContainerLow: "#131313", sContainerHigh: "#202020",
  sContainerHighest: "#262626", sBright: "#2c2c2c",
  primary: "#85adff", primaryDim: "#0070eb",
  secondary: "#59ee50", secondaryDim: "#49e043",
  tertiary: "#deffab", error: "#ff716c",
  outline: "#767575", outlineVar: "#484847",
  onSurface: "#e8e8e8", white: "#ffffff",
};
const F = {
  head: "'Space Grotesk', sans-serif",
  mono: "'JetBrains Mono', monospace",
  body: "'Inter', sans-serif",
};

// Sidebar width as a constant so header/main stay in sync
const SIDEBAR_W = "16rem";

// ── API Layer ──────────────────────────────────────────────────────────────
const api = {
  async get(path: string) { const r = await fetch(path); if (!r.ok) throw new Error(`GET ${path}: ${r.status}`); return r.json(); },
  async post(path: string, body?: any) { const r = await fetch(path, { method: "POST", headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined }); if (!r.ok) throw new Error(`POST ${path}: ${r.status}`); return r.json(); },
  async put(path: string, body: any) { const r = await fetch(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); if (!r.ok) throw new Error(`PUT ${path}: ${r.status}`); return r.json(); },
  async del(path: string) { const r = await fetch(path, { method: "DELETE" }); if (!r.ok) throw new Error(`DELETE ${path}: ${r.status}`); return r.json(); },
};

// ── Types ──────────────────────────────────────────────────────────────────
interface Target { id: string; name: string; source_type: string; source_config: Record<string, any>; match_criteria: string; cadence: string; enabled: boolean; consecutive_failures: number; last_checked_at: string | null; last_hit_at: string | null; created_at: string | null; updated_at: string | null; }
interface Hit { id: string; target_id: string; target_name: string; source_url: string | null; title: string; summary: string; match_reason: string; relevance_score: number; surfaced_at: string; seen: boolean; rating: number | null; }

// ── Utilities ──────────────────────────────────────────────────────────────
function timeAgo(iso: string | null) {
  if (!iso) return "never";
  const d = Date.now() - new Date(iso).getTime(), m = Math.floor(d / 60000);
  if (m < 1) return "just now"; if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`; return `${Math.floor(h / 24)}d ago`;
}
function scoreColor(s: number) { return s >= 0.8 ? T.secondary : s >= 0.6 ? T.primary : s >= 0.4 ? "#ffb86c" : T.outline; }
function targetStatus(t: Target) {
  if (!t.enabled) return { label: "DISABLED", color: T.outlineVar };
  if (t.consecutive_failures >= 3) return { label: "CRITICAL", color: T.error };
  if (t.consecutive_failures >= 1) return { label: "DEGRADED", color: "#ffb86c" };
  return { label: "NOMINAL", color: T.secondary };
}
const CADENCE_OPTS = [
  { label: "Every 4 hours", value: "0 */4 * * *" }, { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Every 12 hours", value: "0 */12 * * *" }, { label: "Daily", value: "0 0 * * *" },
];

// ── Icons ──────────────────────────────────────────────────────────────────
const I = {
  Dashboard: () => <svg width="1.125em" height="1.125em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>,
  Shield: () => <svg width="1.125em" height="1.125em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  Zap: () => <svg width="1.125em" height="1.125em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
  Gear: () => <svg width="1.125em" height="1.125em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  User: () => <svg width="1.25em" height="1.25em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
  Bell: () => <svg width="1.25em" height="1.25em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>,
  Search: () => <svg width="0.875em" height="0.875em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>,
  Plus: () => <svg width="0.875em" height="0.875em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
  Globe: () => <svg width="1.125em" height="1.125em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
  Github: () => <svg width="1.125em" height="1.125em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>,
  Rss: () => <svg width="1.125em" height="1.125em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>,
  Trash: () => <svg width="0.875em" height="0.875em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>,
  Edit: () => <svg width="0.875em" height="0.875em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
  X: () => <svg width="0.875em" height="0.875em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
  EyeOff: () => <svg width="0.875em" height="0.875em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><line x1="1" y1="1" x2="23" y2="23"/></svg>,
  Eye: () => <svg width="0.875em" height="0.875em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
  Refresh: () => <svg width="0.875em" height="0.875em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>,
  Megaphone: () => <svg width="1.125em" height="1.125em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 11v2a1 1 0 0 0 1 1h3l5 4V6L7 10H4a1 1 0 0 0-1 1z"/><path d="M16 8a5 5 0 0 1 0 8"/></svg>,
};

// ── Shared Components ──────────────────────────────────────────────────────
function TacInput({ label, value, onChange, placeholder, multiline, mono }: {
  label?: string; value: string; onChange: (v: string) => void; placeholder?: string; multiline?: boolean; mono?: boolean;
}) {
  const s: React.CSSProperties = { width: "100%", background: T.sContainerHighest, border: "none", borderBottom: `0.0625rem solid ${T.outlineVar}`, padding: "0.75rem 0.875rem", color: T.onSurface, fontFamily: mono ? F.mono : F.body, fontSize: "0.8125rem", outline: "none", resize: multiline ? "vertical" : undefined };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
      {label && <label style={{ fontFamily: F.head, fontSize: "0.625rem", fontWeight: 700, letterSpacing: "0.12em", color: T.primary, textTransform: "uppercase" }}>{label}</label>}
      {multiline ? <textarea rows={3} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} style={s} onFocus={e => (e.target as HTMLElement).style.borderBottomColor = T.secondary} onBlur={e => (e.target as HTMLElement).style.borderBottomColor = T.outlineVar} />
        : <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} style={s} onFocus={e => (e.target as HTMLElement).style.borderBottomColor = T.secondary} onBlur={e => (e.target as HTMLElement).style.borderBottomColor = T.outlineVar} />}
    </div>);
}
function TacSelect({ label, value, onChange, options }: { label?: string; value: string; onChange: (v: string) => void; options: { label: string; value: string }[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
      {label && <label style={{ fontFamily: F.head, fontSize: "0.625rem", fontWeight: 700, letterSpacing: "0.12em", color: T.primary, textTransform: "uppercase" }}>{label}</label>}
      <select value={value} onChange={e => onChange(e.target.value)} style={{ width: "100%", background: T.sContainerHighest, border: "none", borderBottom: `0.0625rem solid ${T.outlineVar}`, padding: "0.75rem 0.875rem", color: T.onSurface, fontFamily: F.body, fontSize: "0.8125rem", outline: "none", cursor: "pointer" }}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>);
}
function Confirm({ msg, onOk, onNo }: { msg: string; onOk: () => void; onNo: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.7)", backdropFilter: "blur(0.25rem)" }} onClick={onNo}>
      <div style={{ background: T.sContainerLow, border: `0.0625rem solid ${T.outlineVar}33`, padding: "2rem", maxWidth: "25rem", width: "90%" }} onClick={e => e.stopPropagation()}>
        <p style={{ fontFamily: F.head, fontSize: "0.875rem", color: T.onSurface, marginBottom: "1.5rem", lineHeight: 1.5 }}>{msg}</p>
        <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
          <button onClick={onNo} style={{ background: T.sContainerHighest, border: "none", padding: "0.625rem 1.25rem", fontFamily: F.head, fontSize: "0.6875rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.outline, cursor: "pointer" }}>Cancel</button>
          <button onClick={onOk} style={{ background: T.error, border: "none", padding: "0.625rem 1.25rem", fontFamily: F.head, fontSize: "0.6875rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.sContainerLowest, fontWeight: 700, cursor: "pointer" }}>Confirm</button>
        </div>
      </div>
    </div>);
}

// ── Sidebar ────────────────────────────────────────────────────────────────
function Sidebar({ view, setView, unseenCount }: { view: string; setView: (v: string) => void; unseenCount: number }) {
  const nav = [{ id: "dashboard", label: "Dashboard", Ic: I.Dashboard }, { id: "watchdog", label: "Watchdog", Ic: I.Shield }, { id: "hits", label: "Intel Feed", Ic: I.Zap, badge: unseenCount }, { id: "marketing", label: "Marketing", Ic: I.Megaphone }, { id: "departments", label: "Departments", Ic: I.Gear }];
  const bs = (_id: string, a: boolean): React.CSSProperties => ({ display: "flex", alignItems: "center", gap: "1rem", padding: "1rem 1.5rem", border: "none", position: "relative", background: a ? T.sContainer : "transparent", borderLeft: a ? `0.125rem solid ${T.secondary}` : "0.125rem solid transparent", color: a ? T.secondary : T.outline, fontFamily: F.head, fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.15em", textTransform: "uppercase", cursor: "pointer", transition: "all 0.2s", textAlign: "left", width: "100%" });
  return (
    <aside style={{ position: "fixed", left: 0, top: 0, height: "100vh", width: SIDEBAR_W, zIndex: 40, background: T.sContainerLow, display: "flex", flexDirection: "column", borderRight: `0.0625rem solid ${T.outlineVar}10` }}>
      <div style={{ padding: "1.5rem 1.5rem 1rem" }}>
        <div style={{ fontFamily: F.head, fontSize: "1.25rem", fontWeight: 900, letterSpacing: "-0.04em", color: T.primary }}>PIA_DISPATCH</div>
        <div style={{ fontFamily: F.head, fontSize: "0.625rem", letterSpacing: "0.2em", color: T.outline, textTransform: "uppercase" }}>RECON_WATCHDOG_DIV</div>
      </div>
      <div style={{ height: "0.0625rem", background: T.sContainerLowest, marginBottom: "1rem" }} />
      <nav style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {nav.map(n => (
          <button key={n.id} onClick={() => setView(n.id)} style={bs(n.id, view === n.id)}
            onMouseEnter={e => { if (view !== n.id) { (e.currentTarget as HTMLElement).style.color = T.onSurface; (e.currentTarget as HTMLElement).style.background = T.sBright; }}}
            onMouseLeave={e => { if (view !== n.id) { (e.currentTarget as HTMLElement).style.color = T.outline; (e.currentTarget as HTMLElement).style.background = "transparent"; }}}>
            <n.Ic /><span>{n.label}</span>
            {(n.badge ?? 0) > 0 && <span style={{ position: "absolute", right: "1.25rem", width: "1.25rem", height: "1.25rem", background: T.secondary, color: T.sContainerLowest, fontFamily: F.mono, fontSize: "0.625rem", fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" }}>{n.badge}</span>}
          </button>))}
        <div style={{ marginTop: "auto" }}>
          <button onClick={() => setView("settings")} style={bs("settings", view === "settings")}
            onMouseEnter={e => { if (view !== "settings") { (e.currentTarget as HTMLElement).style.color = T.onSurface; (e.currentTarget as HTMLElement).style.background = T.sBright; }}}
            onMouseLeave={e => { if (view !== "settings") { (e.currentTarget as HTMLElement).style.color = T.outline; (e.currentTarget as HTMLElement).style.background = "transparent"; }}}>
            <I.Gear /><span>Settings</span>
          </button>
        </div>
      </nav>
      <div style={{ padding: "1.5rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <div style={{ width: "2.5rem", height: "2.5rem", border: `0.0625rem solid ${T.outlineVar}4d`, background: T.sContainer, display: "flex", alignItems: "center", justifyContent: "center" }}><I.User /></div>
        <div>
          <div style={{ fontFamily: F.head, fontSize: "0.625rem", color: T.onSurface, textTransform: "uppercase" }}>Nick</div>
          <div style={{ fontFamily: F.head, fontSize: "0.5625rem", color: T.secondary, textTransform: "uppercase" }}>Authorized</div>
        </div>
      </div>
    </aside>);
}
function Header({ title, unseenCount }: { title: string; unseenCount: number }) {
  return (
    <header style={{ position: "fixed", top: 0, right: 0, left: SIDEBAR_W, height: "4rem", display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 2rem", zIndex: 50, background: `${T.surface}99`, backdropFilter: "blur(0.75rem)", borderBottom: `0.0625rem solid ${T.outlineVar}1a` }}>
      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <h1 style={{ fontFamily: F.head, fontSize: "1.125rem", fontWeight: 900, color: T.white, letterSpacing: "0.1em", textTransform: "uppercase" }}>PIA_RECON_OS</h1>
        <div style={{ height: "1rem", width: "0.0625rem", background: `${T.outlineVar}4d` }} />
        <span style={{ fontFamily: F.head, fontSize: "0.625rem", color: T.primary, letterSpacing: "0.15em" }}>{title}</span>
      </div>
      <button style={{ background: "none", border: "none", color: T.outline, cursor: "pointer", position: "relative" }}>
        <I.Bell />{unseenCount > 0 && <span style={{ position: "absolute", top: 0, right: 0, width: "0.375rem", height: "0.375rem", background: T.secondary }} />}
      </button>
    </header>);
}

// ═══════════════════════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════
function DashboardView({ targets, hits, setView }: { targets: Target[]; hits: Hit[]; setView: (v: string) => void }) {
  const active = targets.filter(t => t.enabled).length, unseen = hits.filter(h => !h.seen).length, fails = targets.reduce((s, t) => s + t.consecutive_failures, 0);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.125rem" }}>
        {[{ l: "Active_Targets", v: active, u: `/${targets.length}`, p: targets.length ? (active / targets.length) * 100 : 0, c: T.secondary },
          { l: "Unseen_Intel", v: unseen, u: "NEW", p: unseen > 0 ? 100 : 0, c: unseen > 0 ? T.secondary : T.outline, pulse: unseen > 0 },
          { l: "Total_Hits", v: hits.length, u: "ALL", p: 60, c: T.primary },
          { l: "Failures", v: fails, u: fails > 0 ? "WARN" : "OK", p: fails * 25, c: fails > 0 ? T.error : T.secondary, pulse: fails > 0 },
        ].map((x, i) => (
          <div key={i} style={{ background: T.sContainerLow, padding: "1.5rem" }}>
            <span style={{ fontFamily: F.head, fontSize: "0.625rem", letterSpacing: "0.15em", color: T.outline, textTransform: "uppercase" }}>{x.l}</span>
            <div style={{ display: "flex", alignItems: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
              <span style={{ fontFamily: F.head, fontSize: "2rem", fontWeight: 700, color: x.c === T.error ? T.error : T.white, lineHeight: 1, animation: x.pulse ? "pulse 2s ease-in-out infinite" : "none" }}>{x.v}</span>
              <span style={{ fontFamily: F.head, fontSize: "0.75rem", color: T.primary, marginBottom: "0.25rem" }}>{x.u}</span>
            </div>
            <div style={{ width: "100%", height: "0.125rem", background: T.sContainerHighest, marginTop: "0.75rem" }}><div style={{ height: "100%", background: x.c, width: `${Math.min(x.p, 100)}%`, transition: "width 0.5s" }} /></div>
          </div>))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 24rem", gap: "0.125rem", minHeight: "30rem" }}>
        <div style={{ background: T.sContainerLow, padding: "0.125rem" }}>
          <div style={{ height: "100%", background: T.surface, padding: "1.5rem", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1.25rem" }}>
              <div><h2 style={{ fontFamily: F.head, fontSize: "1.125rem", fontWeight: 700, color: T.white, textTransform: "uppercase" }}>Target_Grid</h2>
                <p style={{ fontFamily: F.head, fontSize: "0.625rem", color: T.outline, letterSpacing: "0.15em", textTransform: "uppercase" }}>{targets.length} registered</p></div>
              {targets.length > 0 && <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.25rem 0.75rem", background: `${T.secondary}1a`, border: `0.0625rem solid ${T.secondary}33` }}>
                <span style={{ width: "0.5rem", height: "0.5rem", background: T.secondary, borderRadius: "50%", animation: "ping 2s ease-in-out infinite" }} />
                <span style={{ fontFamily: F.head, fontSize: "0.625rem", color: T.secondary, letterSpacing: "0.12em", fontWeight: 700 }}>LIVE</span></div>}
            </div>
            <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column", gap: "0.125rem" }} className="cscroll">
              {targets.length === 0 ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flex: 1, gap: "0.75rem" }}>
                  <p style={{ fontFamily: F.head, fontSize: "0.75rem", color: T.outline, letterSpacing: "0.1em", textTransform: "uppercase" }}>No targets configured</p>
                  <button onClick={() => setView("watchdog")} style={{ background: T.primary, border: "none", padding: "0.625rem 1.5rem", fontFamily: F.head, fontSize: "0.6875rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.sContainerLowest, fontWeight: 700, cursor: "pointer" }}>Add First Target</button>
                </div>
              ) : targets.map(t => { const st = targetStatus(t); return (
                <div key={t.id} onClick={() => setView("watchdog")} style={{ background: T.sContainer, padding: "0.75rem 1rem", display: "flex", alignItems: "center", justifyContent: "space-between", borderLeft: `0.125rem solid ${st.color}`, cursor: "pointer" }}
                  onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = T.sContainerHigh} onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = T.sContainer}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <div style={{ width: "2rem", height: "2rem", background: T.sContainerHighest, display: "flex", alignItems: "center", justifyContent: "center", color: st.color }}>{t.source_type === "rss" ? <I.Rss /> : <I.Github />}</div>
                    <div><h5 style={{ fontFamily: F.head, fontSize: "0.8125rem", fontWeight: 700, color: T.white, textTransform: "uppercase" }}>{t.name}</h5>
                      <p style={{ fontFamily: F.mono, fontSize: "0.5625rem", color: T.outline, marginTop: "0.0625rem" }}>{timeAgo(t.last_checked_at)}</p></div>
                  </div>
                  <span style={{ fontFamily: F.mono, fontSize: "0.625rem", color: st.color, fontWeight: 700 }}>{st.label}</span>
                </div>); })}
            </div>
          </div>
        </div>
        <div style={{ background: T.sContainerLow, display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "1.5rem 1.5rem 1rem", borderBottom: `0.0625rem solid ${T.sContainer}` }}>
            <h2 style={{ fontFamily: F.head, fontSize: "0.875rem", fontWeight: 700, color: T.white, letterSpacing: "0.15em", textTransform: "uppercase" }}>Recent_Intel</h2></div>
          <div style={{ flex: 1, overflowY: "auto" }} className="cscroll">
            {hits.length === 0 ? <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", padding: "2.5rem" }}><p style={{ fontFamily: F.head, fontSize: "0.75rem", color: T.outline, textTransform: "uppercase" }}>No intel yet — run a check</p></div>
              : hits.slice(0, 10).map(h => (
                <div key={h.id} onClick={() => setView("hits")} style={{ padding: "1rem", borderBottom: `0.0625rem solid ${T.outlineVar}0d`, display: "flex", gap: "0.75rem", background: !h.seen ? `${T.primary}0a` : "transparent", cursor: "pointer" }}>
                  <span style={{ fontFamily: F.mono, fontSize: "0.6875rem", fontWeight: 800, color: scoreColor(h.relevance_score), minWidth: "1.75rem" }}>{Math.round(h.relevance_score * 100)}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h6 style={{ fontFamily: F.head, fontSize: "0.75rem", fontWeight: 700, color: T.white, textTransform: "uppercase", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{h.title}</h6>
                    <p style={{ fontFamily: F.mono, fontSize: "0.5625rem", color: T.outline, marginTop: "0.125rem" }}>{h.target_name} · {timeAgo(h.surfaced_at)}</p></div>
                  {!h.seen && <span style={{ width: "0.375rem", height: "0.375rem", background: T.primary, marginTop: "0.25rem", flexShrink: 0 }} />}
                </div>))}
          </div>
          {hits.length > 0 && <div style={{ padding: "1rem", background: T.sContainerHighest }}><button onClick={() => setView("hits")} style={{ width: "100%", textAlign: "center", fontFamily: F.head, fontSize: "0.5625rem", color: T.primary, letterSpacing: "0.2em", textTransform: "uppercase", background: "none", border: "none", cursor: "pointer" }}>View Full Feed →</button></div>}
        </div>
      </div>
    </div>);
}

// ═══════════════════════════════════════════════════════════════════════════
// WATCHDOG — Target CRUD
// ═══════════════════════════════════════════════════════════════════════════
function WatchdogView({ targets, refresh, onRunCheck, checking }: { targets: Target[]; refresh: () => void; onRunCheck: (id?: string) => void; checking: boolean }) {
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<any>({ name: "", source_type: "rss", source_config: { feed_url: "" }, match_criteria: "", cadence: "0 */6 * * *" });
  const [confirm, setConfirm] = useState<{ msg: string; fn: () => void } | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const openNew = () => { setForm({ name: "", source_type: "rss", source_config: { feed_url: "" }, match_criteria: "", cadence: "0 */6 * * *" }); setEditId(null); setShowForm(true); };
  const openEdit = (t: Target) => { setForm({ name: t.name, source_type: t.source_type, source_config: { ...t.source_config }, match_criteria: t.match_criteria, cadence: t.cadence }); setEditId(t.id); setShowForm(true); setExpanded(null); };
  const handleSave = async () => {
    if (!form.name?.trim()) return;
    if (form.source_type === "rss" && !form.source_config?.feed_url?.trim()) return;
    if (form.source_type === "github_api" && (!form.source_config?.owner?.trim() || !form.source_config?.repo?.trim())) return;
    try {
      if (editId) await api.put(`/api/targets/${editId}`, { name: form.name, source_config: form.source_config, match_criteria: form.match_criteria, cadence: form.cadence });
      else await api.post("/api/targets", { name: form.name, source_type: form.source_type, source_config: form.source_config, match_criteria: form.match_criteria, cadence: form.cadence });
      setShowForm(false); setEditId(null); refresh();
    } catch (e) { console.error("Save:", e); }
  };
  const handleDelete = async (id: string) => { try { await api.del(`/api/targets/${id}`); setExpanded(null); refresh(); } catch (e) { console.error(e); } };
  const handleToggle = async (id: string) => { try { await api.post(`/api/targets/${id}/toggle`); refresh(); } catch (e) { console.error(e); } };
  const uf = (k: string, v: any) => setForm((p: any) => ({ ...p, [k]: v }));
  const uc = (k: string, v: any) => setForm((p: any) => ({ ...p, source_config: { ...p.source_config, [k]: v } }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {confirm && <Confirm msg={confirm.msg} onOk={() => { confirm.fn(); setConfirm(null); }} onNo={() => setConfirm(null)} />}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "1rem" }}>
        <div><h3 style={{ fontFamily: F.head, fontSize: "2rem", fontWeight: 700, letterSpacing: "-0.04em", textTransform: "uppercase", color: T.white }}>Watchdog Config</h3>
          <p style={{ fontFamily: F.head, fontSize: "0.75rem", color: T.outline, letterSpacing: "0.15em", marginTop: "0.25rem", textTransform: "uppercase" }}>{targets.length} targets // {targets.filter(t => t.enabled).length} active</p></div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={() => onRunCheck()} disabled={checking} style={{ padding: "0.625rem 1.25rem", background: checking ? T.sContainerHighest : T.secondary, border: "none", fontFamily: F.head, fontSize: "0.6875rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.sContainerLowest, fontWeight: 700, cursor: checking ? "wait" : "pointer", display: "flex", alignItems: "center", gap: "0.5rem", opacity: checking ? 0.6 : 1 }}><I.Refresh /> {checking ? "Running..." : "Run All Checks"}</button>
          <button onClick={openNew} style={{ padding: "0.625rem 1.25rem", background: T.primary, border: "none", fontFamily: F.head, fontSize: "0.6875rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.sContainerLowest, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: "0.5rem" }}><I.Plus /> Register Target</button>
        </div>
      </div>

      {showForm && (
        <div style={{ background: T.sContainerLow, border: `0.0625rem solid ${T.primary}33`, padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h4 style={{ fontFamily: F.head, fontSize: "0.875rem", fontWeight: 700, color: T.primary, letterSpacing: "0.1em", textTransform: "uppercase" }}>{editId ? "Edit Target" : "New Target"}</h4>
            <button onClick={() => setShowForm(false)} style={{ background: "none", border: "none", color: T.outline, cursor: "pointer" }}><I.X /></button></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <TacInput label="Name" value={form.name || ""} onChange={v => uf("name", v)} placeholder="e.g. OpenAI Blog" />
            {!editId && <TacSelect label="Source Type" value={form.source_type} onChange={v => { uf("source_type", v); uf("source_config", v === "rss" ? { feed_url: "" } : { owner: "", repo: "", watch_type: "releases" }); }} options={[{ label: "RSS / Atom Feed", value: "rss" }, { label: "GitHub API", value: "github_api" }]} />}
          </div>
          {form.source_type === "rss"
            ? <TacInput label="Feed URL" value={form.source_config?.feed_url || ""} onChange={v => uc("feed_url", v)} placeholder="https://example.com/rss.xml" mono />
            : <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
                <TacInput label="Owner" value={form.source_config?.owner || ""} onChange={v => uc("owner", v)} placeholder="anthropics" mono />
                <TacInput label="Repo" value={form.source_config?.repo || ""} onChange={v => uc("repo", v)} placeholder="claude-code" mono />
                <TacSelect label="Watch Type" value={form.source_config?.watch_type || "releases"} onChange={v => uc("watch_type", v)} options={[{ label: "Releases", value: "releases" }, { label: "Commits", value: "commits" }]} /></div>}
          <TacInput label="Match Criteria" value={form.match_criteria || ""} onChange={v => uf("match_criteria", v)} placeholder="Natural language description of what to match..." multiline />
          <TacSelect label="Cadence" value={form.cadence} onChange={v => uf("cadence", v)} options={CADENCE_OPTS} />
          <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button onClick={() => setShowForm(false)} style={{ background: T.sContainerHighest, border: "none", padding: "0.625rem 1.5rem", fontFamily: F.head, fontSize: "0.6875rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.outline, cursor: "pointer" }}>Cancel</button>
            <button onClick={handleSave} style={{ background: T.secondary, border: "none", padding: "0.625rem 1.5rem", fontFamily: F.head, fontSize: "0.6875rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.sContainerLowest, fontWeight: 700, cursor: "pointer" }}>{editId ? "Update" : "Register"}</button></div>
        </div>)}

      {targets.length === 0 && !showForm ? (
        <div style={{ background: T.sContainerLow, padding: "4rem", textAlign: "center" }}>
          <p style={{ fontFamily: F.head, fontSize: "0.875rem", color: T.outline, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "0.5rem" }}>No targets configured</p>
          <p style={{ fontFamily: F.body, fontSize: "0.8125rem", color: T.outlineVar, marginBottom: "1rem" }}>Register targets or import seed data from Settings.</p>
          <button onClick={openNew} style={{ background: T.primary, border: "none", padding: "0.75rem 2rem", fontFamily: F.head, fontSize: "0.75rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.sContainerLowest, fontWeight: 700, cursor: "pointer" }}>Register First Target</button></div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.125rem" }}>
          {targets.map(t => { const st = targetStatus(t), isOpen = expanded === t.id; return (
            <div key={t.id} style={{ background: T.sContainerLow, borderLeft: `0.125rem solid ${st.color}`, overflow: "hidden" }}>
              <div style={{ padding: "1rem 1.25rem", display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }} onClick={() => setExpanded(isOpen ? null : t.id)}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.875rem" }}>
                  <div style={{ width: "2.25rem", height: "2.25rem", background: T.sContainerHighest, display: "flex", alignItems: "center", justifyContent: "center", color: st.color }}>{t.source_type === "rss" ? <I.Globe /> : <I.Github />}</div>
                  <div><h5 style={{ fontFamily: F.head, fontSize: "0.875rem", fontWeight: 700, color: t.enabled ? T.white : T.outline, textTransform: "uppercase" }}>{t.name}</h5>
                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.1875rem" }}>
                      <span style={{ fontFamily: F.mono, fontSize: "0.5625rem", color: t.source_type === "rss" ? "#ffb86c" : "#a78bfa", fontWeight: 700, textTransform: "uppercase" }}>{t.source_type === "github_api" ? "GITHUB" : "RSS"}</span>
                      <span style={{ fontFamily: F.mono, fontSize: "0.5625rem", color: T.outline }}>· {t.last_checked_at ? timeAgo(t.last_checked_at) : "unchecked"}</span></div></div></div>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                  <span style={{ fontFamily: F.mono, fontSize: "0.625rem", color: st.color, fontWeight: 700 }}>{st.label}</span>
                  <span style={{ color: T.outlineVar, fontSize: "0.6875rem", transition: "transform 0.2s", transform: isOpen ? "rotate(180deg)" : "none" }}>▼</span></div></div>
              {isOpen && (
                <div style={{ padding: "0 1.25rem 1.25rem", borderTop: `0.0625rem solid ${T.outlineVar}15`, display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "0.75rem" }}>
                    <div><span style={{ fontFamily: F.head, fontSize: "0.5625rem", letterSpacing: "0.15em", color: T.outline, textTransform: "uppercase" }}>Source</span><p style={{ fontFamily: F.mono, fontSize: "0.6875rem", color: T.onSurface, marginTop: "0.125rem", wordBreak: "break-all" }}>{t.source_type === "rss" ? t.source_config?.feed_url : `${t.source_config?.owner}/${t.source_config?.repo} (${t.source_config?.watch_type || "releases"})`}</p></div>
                    <div><span style={{ fontFamily: F.head, fontSize: "0.5625rem", letterSpacing: "0.15em", color: T.outline, textTransform: "uppercase" }}>Cadence</span><p style={{ fontFamily: F.mono, fontSize: "0.6875rem", color: T.onSurface, marginTop: "0.125rem" }}>{t.cadence}</p></div></div>
                  <div><span style={{ fontFamily: F.head, fontSize: "0.5625rem", letterSpacing: "0.15em", color: T.outline, textTransform: "uppercase" }}>Match Criteria</span><p style={{ fontFamily: F.body, fontSize: "0.8125rem", color: T.onSurface, marginTop: "0.25rem", lineHeight: 1.5 }}>{t.match_criteria}</p></div>
                  <div style={{ display: "flex", gap: "0.375rem", marginTop: "0.5rem" }}>
                    <button onClick={() => openEdit(t)} style={{ flex: 1, background: `${T.primary}18`, border: `0.0625rem solid ${T.primary}33`, padding: "0.625rem", fontFamily: F.head, fontSize: "0.625rem", letterSpacing: "0.08em", textTransform: "uppercase", color: T.primary, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.375rem" }}><I.Edit /> Edit</button>
                    <button onClick={() => handleToggle(t.id)} style={{ flex: 1, background: t.enabled ? `${T.error}18` : `${T.secondary}18`, border: `0.0625rem solid ${t.enabled ? T.error : T.secondary}33`, padding: "0.625rem", fontFamily: F.head, fontSize: "0.625rem", letterSpacing: "0.08em", textTransform: "uppercase", color: t.enabled ? T.error : T.secondary, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.375rem" }}>{t.enabled ? <><I.EyeOff /> Disable</> : <><I.Eye /> Enable</>}</button>
                    <button onClick={() => setConfirm({ msg: `Delete "${t.name}"? Hits will also be deleted.`, fn: () => handleDelete(t.id) })} style={{ width: "2.625rem", background: `${T.error}18`, border: `0.0625rem solid ${T.error}33`, padding: "0.625rem", color: T.error, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}><I.Trash /></button>
                    <button onClick={() => onRunCheck(t.id)} disabled={checking} style={{ flex: 1, background: `${T.secondary}18`, border: `0.0625rem solid ${T.secondary}33`, padding: "0.625rem", fontFamily: F.head, fontSize: "0.625rem", letterSpacing: "0.08em", textTransform: "uppercase", color: T.secondary, cursor: checking ? "wait" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.375rem", opacity: checking ? 0.5 : 1 }}><I.Refresh /> Check</button>
                  </div></div>)}
            </div>); })}
        </div>)}
    </div>);
}

// ═══════════════════════════════════════════════════════════════════════════
// INTEL FEED
// ═══════════════════════════════════════════════════════════════════════════
function HitsView({ hits, refresh }: { hits: Hit[]; refresh: () => void }) {
  const [filter, setFilter] = useState("all");
  const [sortBy, setSortBy] = useState("date");
  const [searchQ, setSearchQ] = useState("");
  const [confirm, setConfirm] = useState<{ msg: string; fn: () => void } | null>(null);

  let list = filter === "all" ? hits : filter === "unseen" ? hits.filter(h => !h.seen) : hits.filter(h => h.seen);
  if (searchQ.trim()) { const q = searchQ.toLowerCase(); list = list.filter(h => h.title.toLowerCase().includes(q) || h.summary?.toLowerCase().includes(q) || h.target_name?.toLowerCase().includes(q)); }
  list = [...list].sort((a, b) => sortBy === "score" ? b.relevance_score - a.relevance_score : new Date(b.surfaced_at).getTime() - new Date(a.surfaced_at).getTime());
  const unseen = hits.filter(h => !h.seen).length;

  const handleRate = async (id: string, rating: number) => { try { await api.post(`/api/hits/${id}/rate`, { rating }); refresh(); } catch (e) { console.error(e); } };
  const handleMarkSeen = async (id: string) => { try { await api.post(`/api/hits/${id}/seen`); refresh(); } catch (e) { console.error(e); } };
  const handleMarkAllSeen = async () => { try { await api.post("/api/hits/mark-all-seen"); refresh(); } catch (e) { console.error(e); } };
  const handleDelete = async (id: string) => { try { await api.del(`/api/hits/${id}`); refresh(); } catch (e) { console.error(e); } };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {confirm && <Confirm msg={confirm.msg} onOk={() => { confirm.fn(); setConfirm(null); }} onNo={() => setConfirm(null)} />}
      <div>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: "0.5rem" }}>
          <h2 style={{ fontFamily: F.head, fontSize: "2rem", fontWeight: 900, color: T.white, letterSpacing: "-0.04em", textTransform: "uppercase" }}>Intelligence_Feed</h2>
          {unseen > 0 && <button onClick={handleMarkAllSeen} style={{ background: `${T.primary}18`, border: `0.0625rem solid ${T.primary}33`, padding: "0.375rem 1rem", fontFamily: F.head, fontSize: "0.625rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.primary, cursor: "pointer" }}>Mark All Read ({unseen})</button>}
        </div>
        <div style={{ height: "0.0625rem", background: `linear-gradient(90deg, ${T.primary}80, transparent)` }} /></div>
      <div style={{ display: "flex", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ display: "flex" }}>
          {["all", "unseen", "reviewed"].map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{ background: filter === f ? T.sContainer : "transparent", border: "none", borderBottom: filter === f ? `0.125rem solid ${T.primary}` : "0.125rem solid transparent", padding: "0.625rem 1.25rem", color: filter === f ? T.primary : T.outline, fontFamily: F.head, fontSize: "0.6875rem", fontWeight: 700, letterSpacing: "0.1em", cursor: "pointer", textTransform: "uppercase" }}>{f}{f === "unseen" && unseen > 0 ? ` (${unseen})` : ""}</button>))}
        </div>
        <div style={{ flex: 1 }} />
        <TacSelect value={sortBy} onChange={setSortBy} options={[{ label: "Sort: Newest", value: "date" }, { label: "Sort: Score", value: "score" }]} />
        <div style={{ position: "relative", minWidth: "12.5rem" }}>
          <input value={searchQ} onChange={e => setSearchQ(e.target.value)} placeholder="SEARCH..." style={{ width: "100%", background: T.sContainerHighest, border: "none", borderBottom: `0.0625rem solid ${T.outlineVar}`, padding: "0.625rem 2rem 0.625rem 0.75rem", color: T.onSurface, fontFamily: F.head, fontSize: "0.6875rem", letterSpacing: "0.08em", outline: "none" }} />
          <span style={{ position: "absolute", right: "0.625rem", top: "50%", transform: "translateY(-50%)", color: T.outline }}><I.Search /></span></div></div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.125rem" }}>
        {list.length === 0 ? (
          <div style={{ background: T.sContainerLow, padding: "4rem", textAlign: "center" }}>
            <p style={{ fontFamily: F.head, fontSize: "0.875rem", color: T.outline, letterSpacing: "0.15em", textTransform: "uppercase" }}>{searchQ ? "No matching intel" : hits.length === 0 ? "No intel collected yet — run checks first" : "No hits in this filter"}</p></div>
        ) : list.map(hit => (
          <HitCard key={hit.id} hit={hit} onRate={handleRate} onMarkSeen={handleMarkSeen}
            onDelete={() => setConfirm({ msg: `Delete "${hit.title}"?`, fn: () => handleDelete(hit.id) })} />))}
      </div>
    </div>);
}

function HitCard({ hit, onRate, onMarkSeen, onDelete }: { hit: Hit; onRate: (id: string, r: number) => void; onMarkSeen: (id: string) => void; onDelete: () => void }) {
  const [open, setOpen] = useState(!hit.seen);
  return (
    <div style={{ background: T.sContainerLow, borderLeft: `0.1875rem solid ${scoreColor(hit.relevance_score)}`, display: "grid", gridTemplateColumns: open ? "1fr 11.25rem" : "1fr" }}>
      <div style={{ padding: "1.25rem 1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <span style={{ fontFamily: F.head, fontSize: "0.625rem", color: T.outline, letterSpacing: "0.15em", textTransform: "uppercase" }}>{hit.target_name}</span>
          <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
            <span style={{ fontFamily: F.mono, fontSize: "0.875rem", fontWeight: 800, color: scoreColor(hit.relevance_score), textShadow: hit.relevance_score >= 0.8 ? `0 0 0.5rem ${scoreColor(hit.relevance_score)}66` : "none" }}>{Math.round(hit.relevance_score * 100)}</span>
            {!hit.seen && <button onClick={e => { e.stopPropagation(); onMarkSeen(hit.id); }} title="Mark read" style={{ width: "0.625rem", height: "0.625rem", background: T.primary, boxShadow: `0 0 0.375rem ${T.primary}88`, border: "none", cursor: "pointer", padding: 0 }} />}
          </div></div>
        <h3 onClick={() => setOpen(!open)} style={{ fontFamily: F.head, fontSize: "1rem", fontWeight: 700, color: T.white, margin: 0, lineHeight: 1.3, textTransform: "uppercase", letterSpacing: "-0.02em", cursor: "pointer" }}>{hit.title}</h3>
        <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.375rem", alignItems: "center" }}>
          <span style={{ fontFamily: F.mono, fontSize: "0.5625rem", color: T.outline }}>{timeAgo(hit.surfaced_at)}</span>
          {hit.source_url && <a href={hit.source_url} target="_blank" rel="noopener" style={{ fontFamily: F.head, fontSize: "0.5625rem", color: T.primary, textDecoration: "none", letterSpacing: "0.1em", textTransform: "uppercase" }}>Source →</a>}
          <div style={{ flex: 1 }} />
          <button onClick={onDelete} style={{ background: "none", border: "none", color: T.outlineVar, cursor: "pointer", opacity: 0.5 }}><I.Trash /></button></div>
        {open && (<div style={{ marginTop: "0.875rem" }}>
          <p style={{ fontFamily: F.body, fontSize: "0.8125rem", color: T.outline, lineHeight: 1.6, marginBottom: "0.625rem" }}>{hit.summary}</p>
          <div style={{ fontFamily: F.mono, fontSize: "0.625rem", color: T.outline, padding: "0.5rem 0.625rem", background: T.sContainer }}><span style={{ color: T.primary, fontWeight: 700 }}>MATCH:</span> {hit.match_reason}</div></div>)}
      </div>
      {open && (<div style={{ background: T.sContainer, padding: "1.25rem 1rem", display: "flex", flexDirection: "column", justifyContent: "center", gap: "0.5rem", borderLeft: `0.0625rem solid ${T.outlineVar}1a` }}>
        <span style={{ fontFamily: F.head, fontSize: "0.5625rem", color: T.outline, letterSpacing: "0.2em", textTransform: "uppercase", textAlign: "center" }}>Rate</span>
        {[{ v: 5, l: "EXACT" }, { v: 4, l: "GOOD" }, { v: 3, l: "OK" }, { v: 2, l: "WEAK" }, { v: 1, l: "NOISE" }].map(({ v, l }) => (
          <button key={v} onClick={() => onRate(hit.id, v)} style={{ background: hit.rating === v ? `${T.primary}22` : T.sContainerLow, border: hit.rating === v ? `0.0625rem solid ${T.primary}66` : `0.0625rem solid ${T.outlineVar}22`, padding: "0.4375rem 0.5rem", color: hit.rating === v ? T.primary : T.outline, fontFamily: F.mono, fontSize: "0.6875rem", fontWeight: 800, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span>{v}</span><span style={{ fontFamily: F.head, fontSize: "0.5rem", letterSpacing: "0.08em", textTransform: "uppercase" }}>{l}</span></button>))}
      </div>)}
    </div>);
}

// ═══════════════════════════════════════════════════════════════════════════
// SETTINGS
// ═══════════════════════════════════════════════════════════════════════════
function SettingsView({ targets, hits, refresh }: { targets: Target[]; hits: Hit[]; refresh: () => void }) {
  const [confirm, setConfirm] = useState<{ msg: string; fn: () => void } | null>(null);
  const [status, setStatus] = useState("");
  const handleImportSeed = async () => { try { const r = await api.post("/api/import-seed"); setStatus(`Imported: ${r.added} added, ${r.skipped} skipped`); refresh(); } catch { setStatus("Import failed"); } };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem", maxWidth: "37.5rem" }}>
      {confirm && <Confirm msg={confirm.msg} onOk={() => { confirm.fn(); setConfirm(null); }} onNo={() => setConfirm(null)} />}
      <div><h2 style={{ fontFamily: F.head, fontSize: "1.75rem", fontWeight: 700, color: T.white, textTransform: "uppercase" }}>System_Config</h2>
        <p style={{ fontFamily: F.head, fontSize: "0.75rem", color: T.outline, letterSpacing: "0.12em", marginTop: "0.25rem", textTransform: "uppercase" }}>Data Management // API Backend</p></div>
      <div style={{ background: T.sContainerLow, padding: "1.5rem" }}>
        <h4 style={{ fontFamily: F.head, fontSize: "0.75rem", fontWeight: 700, color: T.primary, letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: "1rem" }}>Database</h4>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
          {[{ l: "Targets", v: targets.length }, { l: "Total Hits", v: hits.length }, { l: "Unseen", v: hits.filter(h => !h.seen).length }].map(s => (
            <div key={s.l}><span style={{ fontFamily: F.head, fontSize: "0.5625rem", letterSpacing: "0.15em", color: T.outline, textTransform: "uppercase" }}>{s.l}</span><p style={{ fontFamily: F.head, fontSize: "1.5rem", fontWeight: 700, color: T.white, marginTop: "0.25rem" }}>{s.v}</p></div>))}
        </div></div>
      <div style={{ background: T.sContainerLow, padding: "1.5rem" }}>
        <h4 style={{ fontFamily: F.head, fontSize: "0.75rem", fontWeight: 700, color: T.primary, letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: "0.5rem" }}>Import Seed Targets</h4>
        <p style={{ fontFamily: F.body, fontSize: "0.8125rem", color: T.outline, lineHeight: 1.5, marginBottom: "1rem" }}>Load default watchdog targets from seed_targets.py. Skips existing by name.</p>
        <button onClick={handleImportSeed} style={{ background: T.secondary, border: "none", padding: "0.625rem 1.5rem", fontFamily: F.head, fontSize: "0.6875rem", letterSpacing: "0.1em", textTransform: "uppercase", color: T.sContainerLowest, fontWeight: 700, cursor: "pointer" }}>Import Seed Targets</button>
        {status && <p style={{ fontFamily: F.mono, fontSize: "0.6875rem", color: T.secondary, marginTop: "0.75rem" }}>{status}</p>}
      </div>
    </div>);
}

// ═══════════════════════════════════════════════════════════════════════════
// LOGIN
// ═══════════════════════════════════════════════════════════════════════════
function LoginView({ onLogin }: { onLogin: () => void }) {
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  useEffect(() => { fetch("/api/health").then(r => setApiOk(r.ok)).catch(() => setApiOk(false)); }, []);
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: T.surface }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1.5rem 2rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ width: "2.5rem", height: "2.5rem", background: T.primary, display: "flex", alignItems: "center", justifyContent: "center" }}><I.Shield /></div>
          <span style={{ fontFamily: F.head, fontWeight: 700, fontSize: "1.25rem", letterSpacing: "-0.04em", color: T.primary }}>PIA_DISPATCH</span></div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div style={{ width: "0.5rem", height: "0.5rem", background: apiOk === true ? T.secondary : apiOk === false ? T.error : T.outline, borderRadius: "50%", animation: apiOk === null ? "pulse 1s ease-in-out infinite" : "none" }} />
          <span style={{ fontFamily: F.head, fontSize: "0.75rem", letterSpacing: "0.15em", color: apiOk === true ? T.secondary : apiOk === false ? T.error : T.outline, textTransform: "uppercase" }}>
            {apiOk === true ? "API_Connected" : apiOk === false ? "API_Offline" : "Checking..."}
          </span></div>
      </header>
      <main style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
        <div style={{ width: "100%", maxWidth: "28.75rem", position: "relative" }}>
          {(["top", "bottom"] as const).map(v => (["left", "right"] as const).map(h => (
            <div key={v + h} style={{ position: "absolute", [v]: "-0.25rem", [h]: "-0.25rem", width: "1.5rem", height: "1.5rem", [`border${v === "top" ? "Top" : "Bottom"}`]: `0.125rem solid ${T.primary}66`, [`border${h === "left" ? "Left" : "Right"}`]: `0.125rem solid ${T.primary}66` }} />)))}
          <section style={{ background: T.sContainerLow, border: `0.0625rem solid ${T.white}0d`, boxShadow: `0 0 2.5rem ${T.primaryDim}14` }}>
            <div style={{ padding: "3rem" }}>
              <h1 style={{ fontFamily: F.head, fontSize: "1.5rem", fontWeight: 700, letterSpacing: "0.05em", color: T.onSurface, textTransform: "uppercase", marginBottom: "0.5rem" }}>Requesting Clearance</h1>
              <p style={{ fontFamily: F.head, fontSize: "0.75rem", color: T.outline, letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: "2.5rem" }}>System: PIA_Recon // Manual_Entry</p>
              {apiOk === false && (
                <div style={{ background: `${T.error}18`, border: `0.0625rem solid ${T.error}33`, padding: "0.75rem 1rem", marginBottom: "1.5rem" }}>
                  <p style={{ fontFamily: F.mono, fontSize: "0.6875rem", color: T.error }}>API server not reachable at localhost:8000</p>
                  <p style={{ fontFamily: F.mono, fontSize: "0.625rem", color: T.outline, marginTop: "0.25rem" }}>Run: uvicorn api:app --host 0.0.0.0 --port 8000 --reload</p></div>)}
              <button onClick={onLogin} disabled={apiOk !== true} style={{ width: "100%", background: apiOk === true ? T.primary : T.sContainerHighest, color: apiOk === true ? T.sContainerLowest : T.outline, padding: "1.25rem", border: "none", fontFamily: F.head, fontWeight: 700, fontSize: "0.875rem", letterSpacing: "0.15em", textTransform: "uppercase", cursor: apiOk === true ? "pointer" : "not-allowed", marginTop: "0.5rem" }}>
                {apiOk === true ? "INITIALIZE_SYNC" : apiOk === false ? "API_REQUIRED" : "CONNECTING..."}
              </button>
            </div>
            <div style={{ height: "0.1875rem", background: `linear-gradient(90deg, ${T.primaryDim}, ${T.secondary}, ${T.primaryDim})`, opacity: 0.5 }} /></section>
        </div>
      </main>
    </div>);
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════
export default function App() {
  const [view, setView] = useState("dashboard");
  const [loggedIn, setLoggedIn] = useState(false);
  const [targets, setTargets] = useState<Target[]>([]);
  const [hits, setHits] = useState<Hit[]>([]);
  const [checking, setChecking] = useState(false);

  const refresh = useCallback(async () => {
    try { const [t, h] = await Promise.all([api.get("/api/targets"), api.get("/api/hits")]); setTargets(t); setHits(h); } catch (e) { console.error("Refresh:", e); }
  }, []);

  useEffect(() => { if (!loggedIn) return; refresh(); const iv = setInterval(refresh, 30000); return () => clearInterval(iv); }, [loggedIn, refresh]);

  const handleRunCheck = async (targetId?: string) => {
    setChecking(true);
    try { await api.post(targetId ? `/api/run-check?target_id=${targetId}` : "/api/run-check"); await refresh(); } catch (e) { console.error("Check:", e); }
    setChecking(false);
  };

  const uc = hits.filter(h => !h.seen).length;
  const titles: Record<string, string> = { dashboard: "DASHBOARD", watchdog: "WATCHDOG_CONFIG", hits: "INTEL_FEED", settings: "SYSTEM_CONFIG" };

  if (!loggedIn) return <LoginView onLogin={() => setLoggedIn(true)} />;

  return (
    <div style={{ minHeight: "100vh", background: T.bg }}>
      <Sidebar view={view} setView={setView} unseenCount={uc} />
      <Header title={titles[view] || ""} unseenCount={uc} />
      <main style={{ marginLeft: SIDEBAR_W, paddingTop: "4rem", minHeight: "100vh" }}>
        <div style={{ padding: "2rem" }}>
          {view === "dashboard" && <DashboardView targets={targets} hits={hits} setView={setView} />}
          {view === "watchdog" && <WatchdogView targets={targets} refresh={refresh} onRunCheck={handleRunCheck} checking={checking} />}
          {view === "hits" && <HitsView hits={hits} refresh={refresh} />}
          {view === "settings" && <SettingsView targets={targets} hits={hits} refresh={refresh} />}
          {view === "marketing" && <MarketingPanel />}
          {view === "departments" && <DepartmentsPanel />}
        </div>
      </main>
    </div>);
}