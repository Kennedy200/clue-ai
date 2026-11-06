"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Asset, fmtBytes, fmtTime, uploadFile } from "@/lib/jobs";

export default function Media() {
  const [items, setItems] = useState<Asset[] | null>(null);
  const [pct, setPct] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const [small, setSmall] = useState(true);
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(() => api<Asset[]>("/media").then(setItems).catch(() => setItems([])), []);
  useEffect(() => { load(); }, [load]);

  async function pick(files: FileList | null) {
    const f = files?.[0];
    if (!f) return;
    setErr(""); setPct(0);
    try { await uploadFile(f, setPct); await load(); } catch (e) { setErr((e as Error).message); }
    setPct(null);
  }
  return (
    <div>
      <h1 className="text-3xl font-bold">Media library</h1>
      <p className="mt-1 text-muted">Your uploads. Uploads are split into small pieces and resume if your connection drops.</p>
      <div className="card mt-5 p-4">
        <button className="btn btn-primary w-full sm:w-auto" onClick={() => input.current?.click()} disabled={pct !== null}>{pct === null ? "Upload a video, image or audio file" : `Uploading ${pct}%`}</button>
        <input ref={input} type="file" accept="video/*,image/*,audio/*" hidden onChange={(e) => pick(e.target.files)} />
        <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={small} onChange={(e) => setSmall(e.target.checked)} /> Save data: show file size before you upload</label>
        {pct !== null && <div className="mt-3 h-2 overflow-hidden rounded-full bg-line"><div className="h-full bg-violet" style={{ width: `${pct}%` }} /></div>}
        {err && <p role="alert" className="mt-2 text-sm text-coral">{err}</p>}
        {small && <p className="mt-2 text-xs text-muted">Tip: a phone video of 1 minute is usually 30 to 100 MB. Upload on Wi-Fi when you can.</p>}
      </div>
      <ul className="mt-6 grid gap-3 sm:grid-cols-2">
        {items?.map((a) => (
          <li key={a.id} className="card flex items-center justify-between gap-3 p-3">
            <div className="min-w-0"><p className="truncate font-medium">{a.name}</p>
              <p className="text-xs text-muted">{a.kind}{a.duration ? ` · ${fmtTime(a.duration)}` : ""} · {fmtBytes(a.size)}{a.attribution ? ` · ${a.attribution}` : ""}</p></div>
            <button className="btn btn-ghost !min-h-9 text-sm" onClick={async () => { await api(`/media/${a.id}`, { method: "DELETE" }); load(); }} aria-label={`Delete ${a.name}`}>Delete</button>
          </li>
        ))}
      </ul>
      {items?.length === 0 && <p className="mt-6 text-muted">Nothing here yet.</p>}
    </div>
  );
}
