"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Row = { row: number; title: string; job_id?: string; project_id?: string; error?: string };
type Kit = { id: string; name: string };

export default function Bulk() {
  const [csv, setCsv] = useState("");
  const [kits, setKits] = useState<Kit[]>([]);
  const [kit, setKit] = useState("");
  const [res, setRes] = useState<Row[] | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api<Kit[]>("/brand-kits").then(setKits).catch(() => {}); }, []);

  const template = async () => { const t = await api<{ csv: string }>("/bulk/template"); setCsv(t.csv); };
  async function run() {
    setErr(""); setRes(null); setBusy(true);
    try { const r = await api<{ created: number; results: Row[] }>("/bulk/text-stories", { body: { csv, brand_kit_id: kit || null } }); setRes(r.results); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold">Bulk create</h1>
      <p className="mt-1 text-sm text-muted">Make up to 25 text-story videos from a spreadsheet. Save it as CSV with the columns <code>title</code> and <code>text</code>. Each video costs 5 credits, checked before anything starts. Included in Business.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn btn-ghost" onClick={template}>Fill in an example</button>
        <label className="btn btn-ghost cursor-pointer">Choose a CSV file<input type="file" accept=".csv,text/csv" className="sr-only" onChange={async (e) => { const f = e.target.files?.[0]; if (f) setCsv(await f.text()); }} /></label>
      </div>
      <label htmlFor="csv" className="mt-3 block text-sm font-medium">CSV</label>
      <textarea id="csv" className="input mt-1 min-h-48 font-mono text-xs" value={csv} onChange={(e) => setCsv(e.target.value)} placeholder={"title,text\nMy story,Stop scrolling…"} />
      {kits.length > 0 && <label className="mt-3 block text-sm font-medium">Brand kit<select className="input mt-1" value={kit} onChange={(e) => setKit(e.target.value)}><option value="">None</option>{kits.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}</select></label>}
      <button className="btn btn-primary mt-4" disabled={busy || csv.trim().length < 5} onClick={run}>{busy ? "Starting…" : "Create all videos"}</button>
      {err && <p role="alert" className="mt-3 rounded-xl bg-coral/10 p-3 text-sm text-coral">{err}</p>}
      {res && (
        <section aria-label="Results" className="mt-5">
          <p role="status" className="font-semibold">{res.filter((r) => r.job_id).length} of {res.length} started. They render one after another; follow them in Videos.</p>
          <ul className="mt-2 divide-y divide-line rounded-2xl border border-line bg-card text-sm">
            {res.map((r) => <li key={r.row} className="flex justify-between gap-3 p-3"><span>Row {r.row}: {r.title}</span>{r.error ? <span className="text-coral">{r.error}</span> : <Link className="underline" href="/app/projects">Queued</Link>}</li>)}
          </ul>
        </section>
      )}
    </div>
  );
}
