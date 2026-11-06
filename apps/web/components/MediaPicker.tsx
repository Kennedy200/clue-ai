"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Asset, fmtBytes, fmtTime, uploadFile } from "@/lib/jobs";

/** Pick a file from the library or upload a new one (chunked and resumable). */
export function MediaPicker({ kinds, value, onChange, label }: { kinds: Asset["kind"][]; value: string | null; onChange: (id: string | null, a?: Asset) => void; label: string }) {
  const [items, setItems] = useState<Asset[]>([]);
  const [pct, setPct] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(() => api<Asset[]>("/media").then((a) => setItems(a.filter((x) => kinds.includes(x.kind)))).catch(() => {}), [kinds]);
  useEffect(() => { load(); }, [load]);

  async function pick(f: File | undefined) {
    if (!f) return;
    setErr(""); setPct(0);
    try {
      const a = await uploadFile(f, setPct);
      await load();
      onChange(a.id, a);
    } catch (e) { setErr((e as Error).message); }
    setPct(null);
  }
  const accept = kinds.map((k) => (k === "video" ? "video/*" : k === "image" ? "image/*" : "audio/*")).join(",");
  return (
    <div>
      <label className="mb-1 block text-sm font-medium" htmlFor={`mp-${label}`}>{label}</label>
      <div className="flex gap-2">
        <select id={`mp-${label}`} className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value || null, items.find((i) => i.id === e.target.value))}>
          <option value="">None</option>
          {items.map((a) => <option key={a.id} value={a.id}>{a.name} · {a.duration ? fmtTime(a.duration) + " · " : ""}{fmtBytes(a.size)}</option>)}
        </select>
        <button type="button" className="btn btn-ghost shrink-0" onClick={() => input.current?.click()} disabled={pct !== null}>{pct === null ? "Upload" : `${pct}%`}</button>
        <input ref={input} type="file" accept={accept} hidden onChange={(e) => pick(e.target.files?.[0])} />
      </div>
      {pct !== null && <div className="mt-2 h-2 overflow-hidden rounded-full bg-line"><div className="h-full bg-violet" style={{ width: `${pct}%` }} /></div>}
      {err && <p role="alert" className="mt-1 text-sm text-coral">{err}</p>}
    </div>
  );
}
