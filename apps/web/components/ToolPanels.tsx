"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Asset, fmtTime } from "@/lib/jobs";
import { FormError } from "./AuthShell";
import { useMe } from "./AppShell";
import { JobView } from "./JobView";
import { MediaPicker } from "./MediaPicker";

export const TOOLS: Record<string, { title: string; blurb: string; cost: string }> = {
  ideas: { title: "Video Idea Generator", blurb: "Your niche in, ten ideas with hook lines out.", cost: "1 credit" },
  title: { title: "Title Scorer", blurb: "Score a title and get five better ones.", cost: "1 credit" },
  enhance: { title: "Script Enhancer", blurb: "Rewrite a script for a stronger hook and tighter pacing.", cost: "1 credit" },
  thumbnails: { title: "Thumbnail Maker", blurb: "Four 1280×720 thumbnail layouts from one title.", cost: "2 credits" },
  voiceover: { title: "AI Voiceover", blurb: "Turn text into an MP3 with a local voice.", cost: "1 credit per ~30 s" },
  transcribe: { title: "Video Transcriber", blurb: "Video or audio to text, with SRT and VTT downloads.", cost: "Free" },
  clips: { title: "Auto Clipping", blurb: "Long video in, the best short clips out, reframed to vertical with captions.", cost: "8 credits + 2 per clip" },
};

function useAction() {
  const { refresh } = useMe();
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function run<T>(fn: () => Promise<T>): Promise<T | null> {
    setErr(""); setBusy(true);
    try { const r = await fn(); refresh(); return r; } catch (e) { setErr((e as Error).message); return null; } finally { setBusy(false); }
  }
  return { err, busy, run };
}

function Ideas() {
  const { err, busy, run } = useAction();
  const [out, setOut] = useState<{ title: string; hook: string; angle?: string }[]>([]);
  return (
    <div>
      <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); const r = await run(() => api<{ ideas: typeof out }>("/ai/ideas", { body: { niche: f.get("niche"), audience: f.get("audience"), tone: f.get("tone") } })); if (r) setOut(r.ideas); }}>
        <FormError msg={err} />
        <label className="block text-sm font-medium">Niche<input name="niche" className="input mt-1" required minLength={2} placeholder="Football in Nigeria" /></label>
        <label className="block text-sm font-medium">Audience (optional)<input name="audience" className="input mt-1" placeholder="Fans aged 18 to 30" /></label>
        <label className="block text-sm font-medium">Tone<select name="tone" className="input mt-1"><option value="standard">Standard</option><option value="nigerian_english">Nigerian English</option><option value="pidgin">Naija Pidgin</option><option value="comedy">Comedy</option></select></label>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Thinking…" : "Get 10 ideas"}</button>
      </form>
      <ol className="mt-6 space-y-3">{out.map((i, n) => <li key={n} className="card p-4"><b>{i.title}</b><p className="mt-1 text-sm">&ldquo;{i.hook}&rdquo;</p>{i.angle && <p className="text-xs text-muted">{i.angle}</p>}</li>)}</ol>
    </div>
  );
}

function Title() {
  const { err, busy, run } = useAction();
  const [r, setR] = useState<{ score: number; verdict: string; strengths: string[]; fixes: string[]; rewrites: string[] } | null>(null);
  return (
    <div>
      <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); const t = String(new FormData(e.currentTarget).get("title")); const x = await run(() => api<NonNullable<typeof r>>("/ai/title-score", { body: { title: t } })); if (x) setR(x); }}>
        <FormError msg={err} />
        <label className="block text-sm font-medium">Your title<input name="title" className="input mt-1" required minLength={3} maxLength={200} /></label>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Scoring…" : "Score it"}</button>
      </form>
      {r && (
        <div className="card mt-6 p-5">
          <p className="font-mono text-5xl font-bold text-violet">{r.score}<span className="text-lg text-muted">/100</span></p>
          <p className="mt-2">{r.verdict}</p>
          {r.fixes.length > 0 && <ul className="mt-3 list-disc pl-5 text-sm">{r.fixes.map((f) => <li key={f}>{f}</li>)}</ul>}
          <h3 className="mt-4 font-semibold">Better versions</h3>
          <ul className="mt-1 space-y-1">{r.rewrites.map((w) => <li key={w} className="rounded-lg bg-line px-3 py-2 text-sm">{w}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

function Enhance() {
  const { err, busy, run } = useAction();
  const [r, setR] = useState<{ script: string; changes: string[]; words: number } | null>(null);
  return (
    <div>
      <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); const x = await run(() => api<NonNullable<typeof r>>("/ai/enhance", { body: { script: f.get("script"), goal: f.get("goal"), seconds: f.get("seconds") ? Number(f.get("seconds")) : null } })); if (x) setR(x); }}>
        <FormError msg={err} />
        <label className="block text-sm font-medium">Your script<textarea name="script" className="input mt-1 py-3" rows={7} required minLength={10} maxLength={5000} /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium">Goal<select name="goal" className="input mt-1"><option value="hook">Stronger hook</option><option value="shorten">Shorten</option><option value="pacing">Fix pacing</option></select></label>
          <label className="block text-sm font-medium">Fit to seconds (optional)<input name="seconds" type="number" min={10} max={180} className="input mt-1" /></label>
        </div>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Rewriting…" : "Enhance"}</button>
      </form>
      {r && <div className="card mt-6 p-5"><p className="whitespace-pre-wrap">{r.script}</p><p className="mt-2 text-xs text-muted">{r.words} words</p>{r.changes.length > 0 && <ul className="mt-3 list-disc pl-5 text-sm">{r.changes.map((c) => <li key={c}>{c}</li>)}</ul>}</div>}
    </div>
  );
}

function Thumbnails() {
  const { err, busy, run } = useAction();
  const [bg, setBg] = useState<string | null>(null);
  const [imgs, setImgs] = useState<{ variant: number; url: string }[]>([]);
  return (
    <div>
      <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); const t = String(new FormData(e.currentTarget).get("title")); const x = await run(() => api<{ thumbnails: typeof imgs }>("/tools/thumbnails", { body: { title: t, background_asset_id: bg } })); if (x) setImgs(x.thumbnails); }}>
        <FormError msg={err} />
        <label className="block text-sm font-medium">Title text<input name="title" className="input mt-1" required maxLength={120} placeholder="I posted 20 videos in 30 days" /></label>
        <MediaPicker kinds={["image"]} value={bg} onChange={(id) => setBg(id)} label="Background photo (optional)" />
        <button className="btn btn-primary" disabled={busy}>{busy ? "Designing…" : "Make 4 thumbnails"}</button>
      </form>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {imgs.map((t) => (
          <figure key={t.variant} className="card overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={t.url} alt={`Thumbnail option ${t.variant + 1}`} width={1280} height={720} className="w-full" />
            <figcaption className="p-3"><a className="btn btn-ghost w-full" href={t.url} download={`thumbnail-${t.variant + 1}.png`}>Download PNG</a></figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}

function Voiceover() {
  const { err, busy, run } = useAction();
  const [voice, setVoice] = useState("af_heart");
  const [voices, setVoices] = useState<{ id: string; name: string; language: string }[]>([]);
  const [text, setText] = useState("");
  const [job, setJob] = useState<string | null>(null);
  useEffect(() => { api<typeof voices>("/voices").then(setVoices).catch(() => {}); }, []);
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  return (
    <div>
      {job ? (
        <JobView jobId={job}>{(j) => <AudioResult path={String(j.result?.output)} />}</JobView>
      ) : (
        <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); const x = await run(() => api<{ job_id: string }>("/tools/voiceover", { body: { text, voice } })); if (x) setJob(x.job_id); }}>
          <FormError msg={err} />
          <label className="block text-sm font-medium">Text<textarea className="input mt-1 py-3" rows={7} value={text} onChange={(e) => setText(e.target.value)} required minLength={2} maxLength={5000} /></label>
          <label className="block text-sm font-medium">Voice<select className="input mt-1" value={voice} onChange={(e) => setVoice(e.target.value)}>{voices.length === 0 && <option>{voice}</option>}{voices.map((v) => <option key={v.id} value={v.id}>{v.name} · {v.language}</option>)}</select></label>
          <p className="text-sm text-muted">{words} words · costs {Math.max(1, Math.ceil(words / 75))} credit(s)</p>
          <button className="btn btn-primary" disabled={busy}>Create voiceover</button>
        </form>
      )}
    </div>
  );
}

function AudioResult({ path }: { path: string }) {
  const url = `/api/files?path=${encodeURIComponent(path)}`;
  const [signed, setSigned] = useState<string | null>(null);
  useEffect(() => { api<{ url: string }>(`/files/sign?path=${encodeURIComponent(path)}`).then((r) => setSigned(r.url)).catch(() => setSigned(null)); }, [path, url]);
  if (!signed) return <p className="text-muted">Preparing audio…</p>;
  return <div className="card p-4"><audio src={signed} controls className="w-full" /><a className="btn btn-primary mt-3 w-full" href={signed} download>Download MP3</a></div>;
}

function Transcribe() {
  const { err, busy, run } = useAction();
  const [asset, setAsset] = useState<string | null>(null);
  const [job, setJob] = useState<string | null>(null);
  return (
    <div>
      {job ? (
        <JobView jobId={job}>{(j) => <TranscriptView id={String(j.result?.transcript_id)} />}</JobView>
      ) : (
        <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); if (!asset) return; const x = await run(() => api<{ job_id: string }>("/tools/transcribe", { body: { asset_id: asset } })); if (x) setJob(x.job_id); }}>
          <FormError msg={err} />
          <MediaPicker kinds={["video", "audio"]} value={asset} onChange={(id) => setAsset(id)} label="Video or audio file" />
          <button className="btn btn-primary" disabled={busy || !asset}>Transcribe</button>
          <p className="text-xs text-muted">Runs on this computer. The first run downloads the speech model once.</p>
        </form>
      )}
    </div>
  );
}

function TranscriptView({ id }: { id: string }) {
  const [t, setT] = useState<{ words: { w: string; start: number; end: number }[]; language: string } | null>(null);
  const [saved, setSaved] = useState("");
  useEffect(() => { api<NonNullable<typeof t>>(`/transcripts/${id}`).then(setT); }, [id]);
  if (!t) return <p className="text-muted">Loading transcript…</p>;
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">Language: {t.language} · {t.words.length} words. Click a word to fix it.</p>
      <div className="card max-h-96 overflow-auto p-4 leading-8">
        {t.words.map((w, i) => (
          <input key={i} aria-label={`Word at ${fmtTime(w.start)}`} value={w.w} size={Math.max(2, w.w.length)} className="mr-1 rounded bg-transparent px-0.5 hover:bg-line focus:bg-line"
            onChange={(e) => setT({ ...t, words: t.words.map((x, j) => (j === i ? { ...x, w: e.target.value } : x)) })} />
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={async () => { await api(`/transcripts/${id}`, { method: "PUT", body: { words: t.words } }); setSaved("Saved."); }}>Save edits</button>
        {["srt", "vtt", "txt"].map((f) => <a key={f} className="btn btn-ghost" href={`/api/transcripts/${id}/download?fmt=${f}`}>Download .{f.toUpperCase()}</a>)}
        <span role="status" className="self-center text-sm text-muted">{saved}</span>
      </div>
    </div>
  );
}

type ClipRow = { id: string; start: number; end: number; length: number; score: number; reason: string; title: string; hook: string; scorer: string; exported: boolean; thumb_url: string | null };

function Clips() {
  const { err, busy, run } = useAction();
  const [asset, setAsset] = useState<string | null>(null);
  const [job, setJob] = useState<string | null>(null);
  const [rows, setRows] = useState<ClipRow[]>([]);
  const [reframe, setReframe] = useState("face");
  const [exp, setExp] = useState<Record<string, string>>({});
  const load = () => asset && api<ClipRow[]>(`/autoclip/${asset}/clips`).then(setRows);
  return (
    <div className="space-y-5">
      <FormError msg={err} />
      {!job && (
        <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); if (!asset) return; const x = await run(() => api<{ job_id: string }>("/autoclip/analyze", { body: { asset_id: asset, count: 8 } })); if (x) setJob(x.job_id); }}>
          <MediaPicker kinds={["video"]} value={asset} onChange={(id) => setAsset(id)} label="Your long video" />
          <button className="btn btn-primary" disabled={busy || !asset}>Find the best clips (8 credits)</button>
          <p className="text-xs text-muted">It transcribes locally, then asks the AI to rank the moments. Without an AI key it still works and says so.</p>
        </form>
      )}
      {job && rows.length === 0 && <JobView jobId={job} onDone={() => load()}>{() => <p className="text-muted">Loading clips…</p>}</JobView>}
      {rows.length > 0 && (
        <>
          <div className="flex items-center gap-2"><label className="text-sm font-medium" htmlFor="rf">Reframe to vertical:</label>
            <select id="rf" className="input !w-auto" value={reframe} onChange={(e) => setReframe(e.target.value)}><option value="face">Follow the face</option><option value="blur">Blurred background</option><option value="center">Centre crop</option></select></div>
          <ul className="space-y-4">
            {rows.map((c) => (
              <li key={c.id} className="card grid gap-3 p-4 sm:grid-cols-[120px_1fr]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                {c.thumb_url ? <img src={c.thumb_url} alt="" className="w-full rounded-xl bg-ink sm:w-[120px]" /> : <div className="h-20 rounded-xl bg-line" />}
                <div>
                  <div className="flex items-start justify-between gap-2"><b>{c.title}</b><span className="rounded-full bg-lime px-2 py-0.5 font-mono text-sm font-bold text-ink" title={c.scorer === "ai" ? "Scored by AI" : "Estimated without AI"}>{c.score}</span></div>
                  <p className="text-xs text-muted">{fmtTime(c.start)}–{fmtTime(c.end)} · {c.length}s · {c.scorer === "ai" ? "AI score" : "estimated"}</p>
                  <p className="mt-1 text-sm"><b>Why this clip:</b> {c.reason}</p>
                  {exp[c.id] ? <JobView jobId={exp[c.id]}>{() => <ClipDownload id={c.id} />}</JobView> : (
                    <button className="btn btn-ghost mt-2 !min-h-9 text-sm" onClick={async () => { const x = await run(() => api<{ job_id: string }>("/autoclip/export", { body: { clip_id: c.id, reframe, captions: true } })); if (x) setExp({ ...exp, [c.id]: x.job_id }); }}>Export (2 credits)</button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function ClipDownload({ id }: { id: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => { api<{ url: string }>(`/autoclip/clips/${id}/download-url`).then((r) => setUrl(r.url)); }, [id]);
  return url ? <div className="mt-2"><video src={url} controls playsInline className="max-h-80 rounded-xl bg-ink" /><a href={url} download className="btn btn-primary mt-2">Download MP4</a></div> : <p className="text-muted">Preparing…</p>;
}

export const PANELS: Record<string, () => React.JSX.Element> = { ideas: Ideas, title: Title, enhance: Enhance, thumbnails: Thumbnails, voiceover: Voiceover, transcribe: Transcribe, clips: Clips };
export type { Asset };
