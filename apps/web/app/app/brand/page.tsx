"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Kit = { id: string; name: string; caption: Record<string, unknown>; watermark: string; outro: string; team_id: string | null; is_default: boolean };
type TeamLite = { id: string; name: string; role: string };
const FONTS = ["Arial", "Impact", "Verdana", "Georgia", "Trebuchet MS"];

export default function BrandPage() {
  const [kits, setKits] = useState<Kit[]>([]);
  const [teams, setTeams] = useState<TeamLite[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [f, setF] = useState({ name: "", font: "Arial", color: "#FFFFFF", highlight: "#C8FF3D", outline: "#000000", uppercase: false, box: false, watermark: "", outro: "", team_id: "" });
  const load = useCallback(async () => { setKits(await api<Kit[]>("/brand-kits")); setTeams(await api<TeamLite[]>("/teams")); }, []);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setMsg("");
    const hex = (c: string) => c.replace("#", "").toUpperCase();
    try {
      await api("/brand-kits", { body: { name: f.name, team_id: f.team_id || null, watermark: f.watermark, outro: f.outro, caption: { font: f.font, color: hex(f.color), highlight: hex(f.highlight), outline: hex(f.outline), uppercase: f.uppercase, box: f.box } } });
      setMsg("Brand kit saved. Apply it from the editor's Captions tab or when creating in bulk.");
      setF({ ...f, name: "" });
      await load();
    } catch (x) { setErr((x as Error).message); }
  }
  const set = (k: string, v: string | boolean) => setF((p) => ({ ...p, [k]: v }));
  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold">Brand kits</h1>
      <p className="mt-1 text-sm text-muted">Save your caption look once and apply it to any video in one tap. Included in Creator and Business.</p>
      <div aria-live="polite">
        {msg && <p role="status" className="mt-3 rounded-xl bg-lime/40 p-3 text-sm">{msg}</p>}
        {err && <p role="alert" className="mt-3 rounded-xl bg-coral/10 p-3 text-sm text-coral">{err}</p>}
      </div>
      <form onSubmit={create} className="card mt-5 grid gap-3 p-4 sm:grid-cols-2">
        <label className="text-sm font-medium sm:col-span-2">Kit name<input className="input mt-1" value={f.name} onChange={(e) => set("name", e.target.value)} required maxLength={80} /></label>
        <label className="text-sm font-medium">Caption font<select className="input mt-1" value={f.font} onChange={(e) => set("font", e.target.value)}>{FONTS.map((x) => <option key={x}>{x}</option>)}</select></label>
        <label className="text-sm font-medium">Text colour<input type="color" className="input mt-1 !p-1" value={f.color} onChange={(e) => set("color", e.target.value)} /></label>
        <label className="text-sm font-medium">Highlight colour<input type="color" className="input mt-1 !p-1" value={f.highlight} onChange={(e) => set("highlight", e.target.value)} /></label>
        <label className="text-sm font-medium">Outline colour<input type="color" className="input mt-1 !p-1" value={f.outline} onChange={(e) => set("outline", e.target.value)} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.uppercase} onChange={(e) => set("uppercase", e.target.checked)} /> UPPERCASE captions</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.box} onChange={(e) => set("box", e.target.checked)} /> Box behind captions</label>
        <label className="text-sm font-medium sm:col-span-2">Closing line (your call to action)<input className="input mt-1" value={f.outro} onChange={(e) => set("outro", e.target.value)} maxLength={120} placeholder="Follow for more tips" /></label>
        {teams.length > 0 && <label className="text-sm font-medium sm:col-span-2">Who can use it<select className="input mt-1" value={f.team_id} onChange={(e) => set("team_id", e.target.value)}><option value="">Only me</option>{teams.map((t) => <option key={t.id} value={t.id}>Team: {t.name}</option>)}</select></label>}
        <div className="sm:col-span-2"><div className="rounded-xl bg-ink p-4 text-center text-2xl font-extrabold" style={{ fontFamily: f.font, color: f.color, WebkitTextStroke: `1px ${f.outline}`, textTransform: f.uppercase ? "uppercase" : "none", background: f.box ? f.outline : undefined }} aria-label="Caption preview">Your <span style={{ color: f.highlight }}>caption</span> look</div></div>
        <button className="btn btn-primary sm:col-span-2">Save brand kit</button>
      </form>
      <h2 className="mt-8 text-xl font-semibold">Your kits</h2>
      {kits.length === 0 ? <p className="mt-2 text-sm text-muted">No kits yet.</p> : (
        <ul className="mt-2 divide-y divide-line rounded-2xl border border-line bg-card text-sm">
          {kits.map((k) => (
            <li key={k.id} className="flex items-center justify-between gap-3 p-3">
              <span><b>{k.name}</b> <span className="text-muted">{k.team_id ? "· team" : "· personal"}</span></span>
              <button className="btn btn-ghost !min-h-9 text-xs" onClick={() => confirm(`Delete ${k.name}?`) && api(`/brand-kits/${k.id}`, { method: "DELETE" }).then(load).catch((e) => setErr(e.message))}>Delete</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
