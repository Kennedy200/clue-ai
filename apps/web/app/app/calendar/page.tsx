"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Post = { id: string; title: string; scheduled_at: string; platform: string; project_id: string | null; notes: string; status: string; external_url: string | null };
type Proj = { id: string; title: string; status: string };
type Pack = { title: string; description: string; hashtags: string[]; download_url: string };
type YT = { configured: boolean; connected: boolean };
const PLATFORMS = ["youtube", "tiktok", "instagram", "facebook", "x", "other"];
const when = (s: string) => new Date(s.endsWith("Z") ? s : s + "Z").toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export default function CalendarPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [projs, setProjs] = useState<Proj[]>([]);
  const [yt, setYt] = useState<YT>({ configured: false, connected: false });
  const [pack, setPack] = useState<{ postId: string; p: Pack } | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [f, setF] = useState({ title: "", at: "", platform: "youtube", project_id: "", notes: "" });

  const load = useCallback(async () => {
    const [p, pr, y] = await Promise.all([api<Post[]>("/calendar"), api<Proj[]>("/projects"), api<YT>("/youtube/status")]);
    setPosts(p); setProjs(pr); setYt(y);
  }, []);
  useEffect(() => {
    load().catch((e) => setErr(e.message));
    const r = new URLSearchParams(window.location.search).get("yt");
    if (r) setMsg(r === "connected" ? "YouTube connected." : "YouTube connection did not complete. Try again.");
  }, [load]);
  async function act(fn: () => Promise<unknown>, ok = "") {
    setErr(""); setMsg("");
    try { await fn(); if (ok) setMsg(ok); await load(); } catch (e) { setErr((e as Error).message); }
  }
  const add = (e: React.FormEvent) => { e.preventDefault(); act(async () => { await api("/calendar", { body: { title: f.title, scheduled_at: new Date(f.at).toISOString(), platform: f.platform, project_id: f.project_id || null, notes: f.notes } }); setF({ ...f, title: "", notes: "" }); }, "Added to your calendar."); };
  const showPack = (p: Post) => act(async () => setPack({ postId: p.id, p: await api<Pack>(`/projects/${p.project_id}/publish-pack`) }));
  const connect = () => act(async () => { const r = await api<{ url: string }>("/youtube/auth-url"); window.location.href = r.url; });
  const publish = (p: Post) => act(async () => {
    const k = await api<Pack>(`/projects/${p.project_id}/publish-pack`);
    await api("/youtube/publish", { body: { project_id: p.project_id, title: p.title, description: k.description, privacy: "private", post_id: p.id } });
  }, "Uploading to YouTube as a private video. Open your calendar again in a minute.");
  const copy = (t: string) => navigator.clipboard?.writeText(t).then(() => setMsg("Copied."));

  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold">Content calendar</h1>
      <p className="mt-1 text-sm text-muted">Plan what you post and when. Posting is by publish pack (copy the title, description and hashtags, download the video){yt.configured ? ", or straight to YouTube once connected" : ""}.</p>
      <div aria-live="polite">
        {msg && <p role="status" className="mt-3 rounded-xl bg-lime/40 p-3 text-sm">{msg}</p>}
        {err && <p role="alert" className="mt-3 rounded-xl bg-coral/10 p-3 text-sm text-coral">{err}</p>}
      </div>
      {yt.configured && <p className="mt-3 text-sm">YouTube: {yt.connected ? <>connected · <button className="underline" onClick={() => act(() => api("/youtube/disconnect", { body: {} }), "Disconnected.")}>disconnect</button></> : <button className="btn btn-ghost !min-h-9" onClick={connect}>Connect YouTube</button>}</p>}

      <form onSubmit={add} className="card mt-5 grid gap-3 p-4 sm:grid-cols-2">
        <label className="text-sm font-medium sm:col-span-2">Title<input className="input mt-1" required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></label>
        <label className="text-sm font-medium">When<input type="datetime-local" className="input mt-1" required value={f.at} onChange={(e) => setF({ ...f, at: e.target.value })} /></label>
        <label className="text-sm font-medium">Where<select className="input mt-1" value={f.platform} onChange={(e) => setF({ ...f, platform: e.target.value })}>{PLATFORMS.map((p) => <option key={p}>{p}</option>)}</select></label>
        <label className="text-sm font-medium sm:col-span-2">Video (optional)<select className="input mt-1" value={f.project_id} onChange={(e) => setF({ ...f, project_id: e.target.value })}><option value="">None yet</option>{projs.filter((p) => p.status === "done").map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></label>
        <button className="btn btn-primary sm:col-span-2">Add to calendar</button>
      </form>

      <h2 className="mt-8 text-xl font-semibold">Coming up</h2>
      {posts.length === 0 ? <p className="mt-2 text-sm text-muted">Nothing planned yet.</p> : (
        <ul className="mt-2 divide-y divide-line rounded-2xl border border-line bg-card text-sm">
          {posts.map((p) => (
            <li key={p.id} className="p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span><b>{p.title}</b> <span className="rounded-full bg-line px-2 py-0.5 text-xs">{p.platform}</span> <span className={`rounded-full px-2 py-0.5 text-xs ${p.status === "published" ? "bg-lime text-ink" : "bg-line"}`}>{p.status}</span><br /><span className="text-muted">{when(p.scheduled_at)}</span>{p.external_url && <> · <a className="underline" href={p.external_url} target="_blank" rel="noreferrer">Open</a></>}</span>
                <span className="flex flex-wrap gap-2">
                  {p.project_id && <button className="btn btn-ghost !min-h-9 text-xs" onClick={() => showPack(p)}>Publish pack</button>}
                  {p.project_id && yt.connected && p.status !== "published" && p.platform === "youtube" && <button className="btn btn-primary !min-h-9 text-xs" onClick={() => publish(p)}>Upload to YouTube</button>}
                  {p.status === "planned" && <button className="btn btn-ghost !min-h-9 text-xs" onClick={() => act(() => api(`/calendar/${p.id}`, { method: "PUT", body: { title: p.title, scheduled_at: p.scheduled_at + "Z", platform: p.platform, project_id: p.project_id, notes: p.notes, status: "published" } }))}>Mark posted</button>}
                  <button className="btn btn-ghost !min-h-9 text-xs" aria-label={`Delete ${p.title}`} onClick={() => act(() => api(`/calendar/${p.id}`, { method: "DELETE" }))}>Delete</button>
                </span>
              </div>
              {pack?.postId === p.id && (
                <div className="mt-3 rounded-xl bg-line p-3" aria-label="Publish pack">
                  <p className="font-medium">{pack.p.title}</p>
                  <pre className="mt-1 whitespace-pre-wrap text-xs">{pack.p.description}</pre>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button className="btn btn-ghost !min-h-9 text-xs" onClick={() => copy(pack.p.title)}>Copy title</button>
                    <button className="btn btn-ghost !min-h-9 text-xs" onClick={() => copy(pack.p.description)}>Copy description</button>
                    <a className="btn btn-primary !min-h-9 text-xs" href={pack.p.download_url} download>Download video</a>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
