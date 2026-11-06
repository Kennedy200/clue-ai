"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { FormError } from "./AuthShell";
import { useMe } from "./AppShell";
import { JobView, VideoResult } from "./JobView";
import { MediaPicker } from "./MediaPicker";

export const STYLE_INFO: Record<string, { title: string; blurb: string }> = {
  text_story: { title: "Text Story", blurb: "Narrated storytime over a looping background with word-highlighted captions." },
  video_story: { title: "Video Story", blurb: "A different picture for every scene. Images come from AI, free photos, or your uploads." },
  commentary: { title: "Video Commentary", blurb: "Your clip with AI commentary on top. The original sound is turned down." },
  split_screen: { title: "Split Screen", blurb: "Your story on top, a satisfying loop underneath to keep people watching." },
  ranking: { title: "Video Ranking", blurb: "A countdown list with big number badges and a one-line verdict each." },
};
const COST: Record<string, number> = { fast: 5, pro: 8, cinematic: 14 };
type Voice = { id: string; name: string; gender: string; language: string };
type Plan = { title: string; hook: string; scenes: { text: string; visual_keywords: string[]; on_screen_text?: string | null }[] };

function VoicePicker({ voice, setVoice }: { voice: string; setVoice: (v: string) => void }) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [err, setErr] = useState("");
  const audio = useRef<HTMLAudioElement>(null);
  useEffect(() => { api<Voice[]>("/voices").then(setVoices).catch((e) => setErr(e.message)); }, []);
  const langs = [...new Set(voices.map((v) => v.language))];
  return (
    <div>
      <label className="mb-1 block text-sm font-medium" htmlFor="voice">Voice</label>
      <div className="flex gap-2">
        <select id="voice" className="input" value={voice} onChange={(e) => setVoice(e.target.value)}>
          {voices.length === 0 && <option value={voice}>{voice}</option>}
          {langs.map((l) => (
            <optgroup key={l} label={l}>
              {voices.filter((v) => v.language === l).map((v) => <option key={v.id} value={v.id}>{v.name} ({v.gender})</option>)}
            </optgroup>
          ))}
        </select>
        <button type="button" className="btn btn-ghost shrink-0" onClick={() => { if (audio.current) { audio.current.src = `/api/voices/${voice}/preview`; audio.current.play().catch(() => setErr("Could not play the preview.")); } }}>▶ Preview</button>
      </div>
      <audio ref={audio} hidden />
      {err && <p className="mt-1 text-sm text-coral">{err}</p>}
    </div>
  );
}

export function CreateForm({ style }: { style: string }) {
  const { me } = useMe();
  const info = STYLE_INFO[style];
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [voice, setVoice] = useState("af_heart");
  const [speed, setSpeed] = useState(1);
  const [mode, setMode] = useState("fast");
  const [captionPos, setCaptionPos] = useState("lower");
  const [bg, setBg] = useState<string | null>(null);
  const [bottom, setBottom] = useState<string | null>(null);
  const [clip, setClip] = useState<string | null>(null);
  const [music, setMusic] = useState<string | null>(null);
  const [imgSrc, setImgSrc] = useState("none");
  const [items, setItems] = useState([{ label: "", text: "" }, { label: "", text: "" }, { label: "", text: "" }]);
  const [idea, setIdea] = useState("");
  const [tone, setTone] = useState("standard");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<{ job_id: string; project_id: string } | null>(null);
  if (!info) return <p>Unknown style.</p>;

  async function generateScript() {
    setErr(""); setBusy(true);
    try {
      const p = await api<Plan>("/ai/plan", { body: { idea, style: style === "ranking" ? "ranking" : style === "text_story" || style === "split_screen" ? "text_story" : style === "commentary" ? "commentary" : "video_story", tone, seconds: 45 } });
      setPlan(p);
      setTitle(p.title);
      setText(p.scenes.map((s) => s.text).join(" "));
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(""); setBusy(true);
    let spec: Record<string, unknown> = {};
    if (style === "text_story") spec = { text, background_asset_id: bg };
    if (style === "split_screen") spec = { text, bottom_asset_id: bottom };
    if (style === "commentary") spec = { clip_asset_id: clip, text };
    if (style === "video_story") spec = plan && text === plan.scenes.map((s) => s.text).join(" ")
      ? { image_source: imgSrc, scenes: plan.scenes.map((s) => ({ text: s.text, keywords: s.visual_keywords, on_screen_text: s.on_screen_text })) }
      : { image_source: imgSrc, text };
    if (style === "ranking") spec = { title: text, items: items.filter((i) => i.label.trim()) };
    try {
      setJob(await api("/render/create", { body: { style, title: title || info.title, spec, voice, speed, mode, music_asset_id: music, caption: { position: captionPos } } }));
    } catch (x) { setErr((x as Error).message); }
    setBusy(false);
  }

  if (job)
    return (
      <div>
        <h1 className="text-2xl font-bold">Making your video</h1>
        <p className="mb-4 text-sm text-muted">You can leave this page. Find the video later under Videos.</p>
        <JobView jobId={job.job_id}>{() => <VideoResult projectId={job.project_id} />}</JobView>
      </div>
    );

  const needsScript = style !== "ranking";
  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h1 className="text-3xl font-bold">{info.title}</h1>
        <p className="mt-1 text-muted">{info.blurb}</p>
      </div>
      <FormError msg={err} />

      {needsScript && (
        <section className="card space-y-3 p-4" aria-label="AI script">
          <label className="block text-sm font-medium" htmlFor="idea">Have only an idea? Let AI write the script (1 credit)</label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input id="idea" className="input" value={idea} onChange={(e) => setIdea(e.target.value)} placeholder="e.g. A man finds his kettle warm in an empty house" maxLength={300} />
            <select aria-label="Tone" className="input sm:w-48" value={tone} onChange={(e) => setTone(e.target.value)}>
              <option value="standard">Standard English</option><option value="nigerian_english">Nigerian English</option>
              <option value="pidgin">Naija Pidgin</option><option value="comedy">Comedy</option><option value="motivational">Motivational</option>
            </select>
            <button type="button" className="btn btn-ghost shrink-0" disabled={busy || idea.trim().length < 3} onClick={generateScript}>Write it</button>
          </div>
          <p className="text-xs text-muted">Uses your free OpenRouter key. If it is not set up, you can still paste your own script below.</p>
        </section>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium" htmlFor="title">Title (for your library)</label>
        <input id="title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} />
      </div>

      {style === "commentary" && <MediaPicker kinds={["video"]} value={clip} onChange={(id) => setClip(id)} label="Your clip" />}

      {style === "ranking" ? (
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium" htmlFor="rtitle">Opening line (optional)</label>
            <input id="rtitle" className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Top 3 Nigerian foods, ranked" />
          </div>
          <p className="text-sm text-muted">List your items best first. The video counts down from the last one.</p>
          {items.map((it, i) => (
            <div key={i} className="card grid gap-2 p-3 sm:grid-cols-[2fr_3fr]">
              <input aria-label={`Item ${i + 1} name`} className="input" placeholder={`#${i + 1} name`} value={it.label} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />
              <input aria-label={`Item ${i + 1} line`} className="input" placeholder="One line about it (optional)" value={it.text} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} />
            </div>
          ))}
          <div className="flex gap-2">
            {items.length < 10 && <button type="button" className="btn btn-ghost" onClick={() => setItems([...items, { label: "", text: "" }])}>Add item</button>}
            {items.length > 2 && <button type="button" className="btn btn-ghost" onClick={() => setItems(items.slice(0, -1))}>Remove last</button>}
          </div>
        </div>
      ) : (
        <div>
          <label className="mb-1 block text-sm font-medium" htmlFor="text">{style === "commentary" ? "Your commentary" : style === "split_screen" ? "Text to narrate" : "Script / story"}</label>
          <textarea id="text" className="input py-3" rows={8} value={text} onChange={(e) => setText(e.target.value)} required minLength={5} maxLength={6000} placeholder="Paste or write it here…" />
          <p className="mt-1 text-xs text-muted">{text.trim() ? text.trim().split(/\s+/).length : 0} words · about {Math.round((text.trim() ? text.trim().split(/\s+/).length : 0) / 2.5)} seconds spoken</p>
        </div>
      )}

      {style === "split_screen" && <MediaPicker kinds={["video", "image"]} value={bottom} onChange={(id) => setBottom(id)} label="Bottom loop (optional, a generated loop is used if empty)" />}
      {style === "text_story" && <MediaPicker kinds={["video", "image"]} value={bg} onChange={(id) => setBg(id)} label="Background (optional)" />}
      {style === "video_story" && (
        <div>
          <label className="mb-1 block text-sm font-medium" htmlFor="img">Pictures</label>
          <select id="img" className="input" value={imgSrc} onChange={(e) => setImgSrc(e.target.value)}>
            <option value="none">Generated backgrounds (fast, always works)</option>
            <option value="ai">AI images (slower, best effort)</option>
            <option value="photos">Free photos from Wikimedia Commons (credits added for you)</option>
          </select>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <VoicePicker voice={voice} setVoice={setVoice} />
        <div>
          <label className="mb-1 block text-sm font-medium" htmlFor="speed">Speed: {speed.toFixed(1)}×</label>
          <input id="speed" className="w-full" type="range" min={0.7} max={1.4} step={0.1} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium" htmlFor="cap">Captions</label>
          <select id="cap" className="input" value={captionPos} onChange={(e) => setCaptionPos(e.target.value)}>
            <option value="lower">Lower third</option><option value="middle">Middle of the screen</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium" htmlFor="mode">Quality</label>
          <select id="mode" className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="fast">Fast, up to 60 s (5 credits)</option>
            <option value="pro">Pro, up to 3 min, music (8 credits)</option>
            <option value="cinematic">Cinematic, up to 3 min (14 credits)</option>
          </select>
        </div>
      </div>
      {mode !== "fast" && <MediaPicker kinds={["audio"]} value={music} onChange={(id) => setMusic(id)} label="Background music (lowers automatically under the voice)" />}

      <div className="card sticky bottom-20 flex items-center justify-between gap-3 p-3 sm:static">
        <p className="text-sm">This costs <b className="font-mono">{COST[mode]}</b> credits{me.mode === "self_host" ? " (unlimited in self-host mode)" : ` · you have ${me.credits}`}</p>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Starting…" : "Create video"}</button>
      </div>
    </form>
  );
}
