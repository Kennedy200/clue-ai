"use client";
import { useEffect, useState } from "react";
import { FormError } from "@/components/AuthShell";
import { useMe } from "@/components/AppShell";
import { VoicePicker } from "@/components/CreateForm";
import { JobView } from "@/components/JobView";
import { MediaPicker } from "@/components/MediaPicker";
import { api } from "@/lib/api";
import { useEditor } from "@/lib/editorStore";
import { Asset } from "@/lib/jobs";
import { CAPTION_PRESETS, PALETTES, editWord, locate, minDuration, move, newId, patchScene, remove, duplicate, splitPoint, splitText, total } from "@/lib/scene";
import type { Scene, Word } from "@/lib/scene";

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9\s]/g, "").replace(/\s+/g, " ").trim();
type VoiceOut = { audio_path: string; duration: number; words: Word[]; url: string };

function useVoice() {
  const [voice, setVoice] = useState("af_heart");
  const [speed, setSpeed] = useState(1);
  useEffect(() => { try { setVoice(localStorage.getItem("clue-voice") || "af_heart"); } catch { /* ignore */ } }, []);
  return { voice, speed, setSpeed, setVoice: (v: string) => { setVoice(v); try { localStorage.setItem("clue-voice", v); } catch { /* ignore */ } } };
}

function Label({ children, htmlFor }: { children: React.ReactNode; htmlFor?: string }) {
  return <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium">{children}</label>;
}

// ---- visual picker ---------------------------------------------------------------------------

type Found = { provider: string; url: string; title: string; author: string; license: string; page_url: string };

function VisualPicker({ index, which }: { index: number; which: "visual" | "visual2" }) {
  const { scene, edit, addFiles } = useEditor();
  const [tab, setTab] = useState<"bg" | "photos" | "ai" | "mine">("bg");
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Found[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [mine, setMine] = useState<Asset[]>([]);
  const cur = scene!.scenes[index][which];
  const apply = (v: NonNullable<Scene["visual"]>) => edit((s) => patchScene(s, index, { [which]: v } as Partial<Scene>), { merge: false });

  useEffect(() => { if (tab === "mine") api<Asset[]>("/media").then((a) => setMine(a.filter((x) => x.kind !== "audio"))).catch(() => {}); }, [tab]);

  async function search(source: "photos" | "ai") {
    setErr(""); setBusy(true); setFound([]);
    try { setFound(await api<Found[]>("/assets/search", { body: { q, source } })); } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }
  async function pick(f: Found) {
    setErr(""); setBusy(true);
    try {
      const a = await api<{ id: string; path: string; attribution: string }>("/assets/import", { body: f });
      const u = await api<{ url: string }>(`/files/sign?path=${encodeURIComponent(a.path)}`);
      addFiles({ [a.path]: u.url });
      apply({ kind: "image", path: a.path, seed: 0, attribution: a.attribution, start: 0, has_audio: false, audio_volume: null });
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }
  async function useMine(a: Asset) {
    const u = await api<{ url: string }>(`/media/${a.id}/url`);
    addFiles({ [a.path]: u.url });
    apply({ kind: a.kind === "video" ? "video" : "image", path: a.path, seed: 0, attribution: null, start: 0, has_audio: a.has_audio, audio_volume: null });
  }

  return (
    <div className="space-y-2">
      <div role="tablist" aria-label="Where the picture comes from" className="flex gap-1 text-sm">
        {([["bg", "Background"], ["photos", "Photos"], ["ai", "AI image"], ["mine", "My media"]] as const).map(([k, t]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`rounded-lg px-3 py-1.5 ${tab === k ? "bg-violet text-white" : "bg-line"}`} onClick={() => setTab(k)}>{t}</button>
        ))}
      </div>
      <FormError msg={err} />
      {tab === "bg" && (
        <div className="flex flex-wrap gap-2">
          {PALETTES.map(([a, b], i) => (
            <button key={i} aria-label={`Background ${i + 1}`} className={`h-12 w-12 rounded-xl border-2 ${cur?.kind === "procedural" && cur.seed % 8 === i ? "border-lime" : "border-transparent"}`}
              style={{ background: `linear-gradient(135deg,#${a},#${b})` }} onClick={() => apply({ kind: "procedural", path: null, seed: i, attribution: null, start: 0, has_audio: false, audio_volume: null })} />
          ))}
        </div>
      )}
      {(tab === "photos" || tab === "ai") && (
        <>
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); search(tab); }}>
            <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={tab === "photos" ? "Search free photos, e.g. Lagos market" : "Describe the picture"} aria-label="Search" minLength={2} required />
            <button className="btn btn-ghost shrink-0" disabled={busy}>{busy ? "…" : "Search"}</button>
          </form>
          {tab === "ai" && <p className="text-xs text-muted">AI images are slow and best effort. They are made on request and may be rate limited.</p>}
          <div className="grid grid-cols-3 gap-2">
            {found.map((f) => (
              <button key={f.url} className="overflow-hidden rounded-xl border border-line" onClick={() => pick(f)} disabled={busy} title={`${f.title} ${f.license}`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={f.url} alt={f.title} loading="lazy" className="aspect-[3/4] w-full object-cover" />
                <span className="block truncate px-1 py-0.5 text-[10px] text-muted">{f.license || "AI"}</span>
              </button>
            ))}
          </div>
        </>
      )}
      {tab === "mine" && (
        <ul className="max-h-48 space-y-1 overflow-auto">
          {mine.length === 0 && <li className="text-sm text-muted">No uploads yet. Add some in Media.</li>}
          {mine.map((a) => <li key={a.id}><button className="w-full rounded-lg bg-line px-3 py-2 text-left text-sm" onClick={() => useMine(a)}>{a.kind === "video" ? "🎞 " : "🖼 "}{a.name}</button></li>)}
        </ul>
      )}
      {cur?.attribution && <p className="text-[11px] text-muted">Credit: {cur.attribution}</p>}
    </div>
  );
}

// ---- scene -----------------------------------------------------------------------------------

export function ScenePanel() {
  const { scene, selected, time, id, edit, addFiles, select, seek } = useEditor();
  const { refresh } = useMe();
  const { voice, speed } = useVoice();
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmSplit, setConfirmSplit] = useState(false);
  if (!scene) return null;
  const sc = scene.scenes[selected];
  const stale = norm(sc.words.map((w) => w.w).join(" ")) !== norm(sc.text);
  const set = (p: Partial<Scene>, merge = true) => edit((s) => patchScene(s, selected, p), { merge });

  async function revoice(i: number, text: string): Promise<VoiceOut> {
    const r = await api<VoiceOut>(`/projects/${id}/scene-voice`, { body: { text, voice, speed } });
    addFiles({ [r.audio_path]: r.url });
    return r;
  }
  async function doRevoice() {
    setErr(""); setBusy(true);
    try {
      const r = await revoice(selected, sc.text);
      edit((s) => patchScene(s, selected, { audio_path: r.audio_path, duration: r.duration, words: r.words }), { merge: false });
      refresh();
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }
  async function doSplit() {
    setConfirmSplit(false); setErr(""); setBusy(true);
    try {
      const loc = locate(scene!, time);
      const at = splitPoint(sc, loc.index === selected ? loc.local : sc.duration / 2);
      if (!at) throw new Error("This scene is too short to split.");
      const [a, b] = splitText(sc.text, at);
      const [ra, rb] = [await revoice(selected, a), await revoice(selected, b)];
      edit((s) => {
        const first: Scene = { ...sc, text: a, audio_path: ra.audio_path, duration: ra.duration, words: ra.words };
        const second: Scene = { ...structuredClone(sc), id: newId(), text: b, audio_path: rb.audio_path, duration: rb.duration, words: rb.words, on_screen_text: null, badge: null };
        const scenes = [...s.scenes];
        scenes.splice(selected, 1, first, second);
        return { ...s, scenes };
      }, { merge: false });
      refresh();
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }

  return (
    <div className="space-y-4">
      <FormError msg={err} />
      <div>
        <Label htmlFor="sc-text">What the narrator says</Label>
        <textarea id="sc-text" className="input py-2" rows={4} value={sc.text} onChange={(e) => set({ text: e.target.value })} maxLength={1200} />
        {stale && (
          <div role="status" className="mt-2 rounded-xl bg-lime/40 p-3 text-sm">
            The voice still says the old words.
            <button className="btn btn-primary mt-2 w-full !min-h-10" onClick={doRevoice} disabled={busy || !sc.text.trim()}>{busy ? "Working…" : "Re-voice this scene (1 credit)"}</button>
          </div>
        )}
      </div>
      <div>
        <Label htmlFor="sc-dur">Length: {sc.duration.toFixed(1)} s</Label>
        <input id="sc-dur" type="range" className="w-full" min={minDuration(sc)} max={30} step={0.1} value={Math.max(sc.duration, minDuration(sc))} onChange={(e) => set({ duration: Number(e.target.value) })} />
        <p className="text-xs text-muted">Shorter than {minDuration(sc).toFixed(1)} s would cut the voice off.</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><Label htmlFor="sc-tr">Transition</Label><select id="sc-tr" className="input" value={sc.transition} onChange={(e) => set({ transition: e.target.value as Scene["transition"] }, false)}><option value="cut">Cut</option><option value="fade">Fade through black</option></select></div>
        <div><Label htmlFor="sc-b">Badge</Label><input id="sc-b" className="input" value={sc.badge ?? ""} maxLength={4} placeholder="e.g. 3" onChange={(e) => set({ badge: e.target.value || null })} /></div>
      </div>
      <div><Label htmlFor="sc-ost">Title on screen</Label><input id="sc-ost" className="input" value={sc.on_screen_text ?? ""} maxLength={60} onChange={(e) => set({ on_screen_text: e.target.value || null })} /></div>
      <div>
        <Label>Picture{scene.layout === "split" ? " (top half)" : ""}</Label>
        <VisualPicker index={selected} which="visual" />
      </div>
      {scene.layout === "split" && <div><Label>Bottom half loop</Label><VisualPicker index={selected} which="visual2" /></div>}
      {sc.visual.kind === "video" && (
        <div>
          <Label htmlFor="sc-vs">Start the clip at (seconds)</Label>
          <input id="sc-vs" type="number" min={0} step={0.5} className="input" value={sc.visual.start} onChange={(e) => set({ visual: { ...sc.visual, start: Math.max(0, Number(e.target.value)) } })} />
          {sc.visual.has_audio && (
            <><Label htmlFor="sc-va">Original sound: {Math.round((sc.visual.audio_volume ?? 0) * 100)}%</Label>
              <input id="sc-va" type="range" className="w-full" min={0} max={1} step={0.05} value={sc.visual.audio_volume ?? 0} onChange={(e) => set({ visual: { ...sc.visual, audio_volume: Number(e.target.value) || null } })} /></>
          )}
        </div>
      )}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Scene actions">
        <button className="btn btn-ghost !min-h-10 text-sm" disabled={selected === 0} onClick={() => { edit((s) => move(s, selected, selected - 1), { merge: false }); select(selected - 1); }}>← Earlier</button>
        <button className="btn btn-ghost !min-h-10 text-sm" disabled={selected >= scene.scenes.length - 1} onClick={() => { edit((s) => move(s, selected, selected + 1), { merge: false }); select(selected + 1); }}>Later →</button>
        <button className="btn btn-ghost !min-h-10 text-sm" onClick={() => { edit((s) => duplicate(s, selected), { merge: false }); select(selected + 1); }}>Duplicate</button>
        {confirmSplit
          ? <button className="btn btn-primary !min-h-10 text-sm" onClick={doSplit} disabled={busy}>Confirm split (2 credits)</button>
          : <button className="btn btn-ghost !min-h-10 text-sm" onClick={() => setConfirmSplit(true)} disabled={busy || sc.text.trim().split(/\s+/).length < 2}>Split at playhead</button>}
        <button className="btn btn-ghost !min-h-10 text-sm text-coral" disabled={scene.scenes.length <= 1} onClick={() => { edit((s) => remove(s, selected), { merge: false }); seek(0); }}>Delete scene</button>
      </div>
    </div>
  );
}

// ---- captions --------------------------------------------------------------------------------

export function CaptionsPanel() {
  const { scene, selected, edit } = useEditor();
  if (!scene) return null;
  const c = scene.captions;
  const setC = (p: Partial<typeof c>, merge = true) => edit((s) => ({ ...s, captions: { ...s.captions, ...p } }), { merge });
  const sc = scene.scenes[selected];
  return (
    <div className="space-y-4">
      <div role="radiogroup" aria-label="Caption style" className="grid grid-cols-2 gap-2">
        {Object.entries(CAPTION_PRESETS).map(([k, p]) => (
          <button key={k} role="radio" aria-checked={c.name === k} onClick={() => setC({ ...p, name: k }, false)}
            className={`rounded-xl border-2 px-3 py-2 text-left text-sm ${c.name === k ? "border-violet bg-violet/10" : "border-line"}`}>
            <span className="font-bold" style={{ color: `#${p.color === "FFFFFF" || p.box ? "6C4DFF" : "111"}` }}>{p.label}</span>
            {p.animate === "pop" && <span className="ml-1 text-[10px] text-muted">(animated in Pro)</span>}
          </button>
        ))}
      </div>
      <div><Label htmlFor="cp-size">Size: {c.size}</Label><input id="cp-size" type="range" className="w-full" min={40} max={150} value={c.size} onChange={(e) => setC({ size: Number(e.target.value) })} /></div>
      <div><Label htmlFor="cp-wpc">Words at a time: {c.words_per_chunk}</Label><input id="cp-wpc" type="range" className="w-full" min={1} max={8} value={c.words_per_chunk} onChange={(e) => setC({ words_per_chunk: Number(e.target.value) })} /></div>
      <div className="grid grid-cols-3 gap-3">
        {([["color", "Text"], ["highlight", "Active word"], ["outline", c.box ? "Box" : "Outline"]] as const).map(([k, t]) => (
          <div key={k}><Label htmlFor={`cp-${k}`}>{t}</Label>
            <input id={`cp-${k}`} type="color" className="h-11 w-full rounded-lg border border-line bg-card" value={`#${c[k]}`} onChange={(e) => setC({ [k]: e.target.value.slice(1).toUpperCase() })} /></div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><Label htmlFor="cp-pos">Position</Label><select id="cp-pos" className="input" value={c.position} onChange={(e) => setC({ position: e.target.value as "lower" | "middle" }, false)}><option value="lower">Lower third</option><option value="middle">Middle</option></select></div>
        <div><Label htmlFor="cp-anim">Animation</Label><select id="cp-anim" className="input" value={c.animate} onChange={(e) => setC({ animate: e.target.value as "none" | "pop" }, false)}><option value="none">None</option><option value="pop">Pop (Pro and Cinematic)</option></select></div>
      </div>
      <div className="flex gap-4 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={c.uppercase} onChange={(e) => setC({ uppercase: e.target.checked }, false)} /> UPPERCASE</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={c.box} onChange={(e) => setC({ box: e.target.checked }, false)} /> Box behind text</label>
      </div>
      <div>
        <Label>Fix words in scene {selected + 1}</Label>
        <p className="mb-2 text-xs text-muted">Spelling only. The timing stays, so captions stay in sync.</p>
        <div className="flex max-h-40 flex-wrap gap-1 overflow-auto rounded-xl bg-line/60 p-2">
          {sc.words.map((w, i) => (
            <input key={`${sc.id}-${i}`} aria-label={`Word ${i + 1}`} value={w.w} size={Math.max(2, w.w.length)} className="rounded bg-card px-1 text-sm"
              onChange={(e) => edit((s) => editWord(s, selected, i, e.target.value), { merge: true })} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ---- voice -----------------------------------------------------------------------------------

export function VoicePanel() {
  const { scene, id, flush } = useEditor();
  const { refresh } = useMe();
  const v = useVoice();
  const [job, setJob] = useState<string | null>(null);
  const [err, setErr] = useState("");
  if (!scene) return null;
  const words = scene.scenes.reduce((a, s) => a + s.text.split(/\s+/).length, 0);
  return (
    <div className="space-y-4">
      <FormError msg={err} />
      <VoicePicker voice={v.voice} setVoice={v.setVoice} />
      <div><Label htmlFor="vp-speed">Speed: {v.speed.toFixed(1)}×</Label><input id="vp-speed" type="range" className="w-full" min={0.7} max={1.4} step={0.1} value={v.speed} onChange={(e) => v.setSpeed(Number(e.target.value))} /></div>
      <p className="text-sm text-muted">This voice and speed are also used when you re-voice a single scene. Re-voicing the whole video costs {Math.max(1, Math.ceil(words / 75))} credit(s).</p>
      {job ? (
        <JobView jobId={job} onDone={(j) => { if (j.status === "done") { void useEditor.getState().load(id); refresh(); } }}>{() => <p role="status" className="rounded-xl bg-lime/40 p-3 text-sm">Done. Every scene has the new voice.</p>}</JobView>
      ) : (
        <button className="btn btn-primary w-full" onClick={async () => { setErr(""); if (!(await flush())) { setErr("Fix the save problem first."); return; } try { setJob((await api<{ job_id: string }>(`/projects/${id}/regen-voice`, { body: { voice: v.voice, speed: v.speed } })).job_id); } catch (e) { setErr((e as Error).message); } }}>Re-voice the whole video</button>
      )}
    </div>
  );
}

// ---- music -----------------------------------------------------------------------------------

export function MusicPanel() {
  const { scene, edit, addFiles } = useEditor();
  if (!scene) return null;
  return (
    <div className="space-y-4">
      <MediaPicker kinds={["audio"]} label="Background music" value={null} onChange={async (aid, a) => {
        if (!aid || !a) { edit((s) => ({ ...s, music_path: null }), { merge: false }); return; }
        const u = await api<{ url: string }>(`/media/${aid}/url`);
        addFiles({ [a.path]: u.url });
        edit((s) => ({ ...s, music_path: a.path }), { merge: false });
      }} />
      <p className="text-sm">{scene.music_path ? <>Music is on: <code className="text-xs">{scene.music_path.split("/").pop()}</code></> : "No music yet. Pick a track you own or have a licence for."}</p>
      {scene.music_path && <button className="btn btn-ghost !min-h-10 text-sm" onClick={() => edit((s) => ({ ...s, music_path: null }), { merge: false })}>Remove music</button>}
      <div><Label htmlFor="mp-vol">Music volume: {Math.round(scene.music_volume * 100)}%</Label><input id="mp-vol" type="range" className="w-full" min={0.02} max={0.5} step={0.01} value={scene.music_volume} onChange={(e) => edit((s) => ({ ...s, music_volume: Number(e.target.value) }))} /></div>
      <p className="text-xs text-muted">Music lowers automatically while the narrator speaks (ducking). It plays in Pro and Cinematic renders. The preview here does not play music.</p>
    </div>
  );
}

// ---- export ----------------------------------------------------------------------------------

type Version = { id: string; version: number; at: string; scenes: number };

export function ExportPanel() {
  const { scene, id, flush, load, output, save } = useEditor();
  const { me, refresh } = useMe();
  const [mode, setMode] = useState<"fast" | "pro" | "cinematic">("fast");
  const [job, setJob] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [versions, setVersions] = useState<Version[]>([]);
  useEffect(() => { api<Version[]>(`/projects/${id}/versions`).then(setVersions).catch(() => {}); }, [id, save]);
  if (!scene) return null;
  const len = total(scene);
  const cost = { fast: 5, pro: 8, cinematic: 14 }[mode];
  const cap = mode === "fast" ? 60 : 180;
  const over = len > cap + 0.5;
  return (
    <div className="space-y-4">
      <FormError msg={err} />
      <div role="radiogroup" aria-label="Quality" className="space-y-2">
        {([["fast", "Fast", "Up to 60 s. Cuts and fades, standard captions.", 5], ["pro", "Pro", "Up to 3 min. Music ducking and animated captions.", 8], ["cinematic", "Cinematic", "Up to 3 min. Colour grade, vignette and film grain.", 14]] as const).map(([k, t, d, c]) => (
          <label key={k} className={`flex cursor-pointer items-start gap-3 rounded-xl border-2 p-3 ${mode === k ? "border-violet bg-violet/10" : "border-line"}`}>
            <input type="radio" name="mode" checked={mode === k} onChange={() => setMode(k)} className="mt-1" />
            <span><b>{t}</b> · {c} credits<br /><span className="text-sm text-muted">{d}</span></span>
          </label>
        ))}
      </div>
      {over && <p role="alert" className="rounded-xl bg-coral/10 p-3 text-sm text-coral">This video is {len.toFixed(0)} s, longer than {mode} mode allows ({cap} s). Shorten it or pick Pro.</p>}
      <p className="text-sm">Cost: <b className="font-mono">{cost}</b> credits{me.mode === "self_host" ? " (unlimited in self-host mode)" : ` · you have ${me.credits}`}</p>
      {job ? (
        <JobView jobId={job} onDone={(j) => { if (j.status !== "queued" && j.status !== "running") { void load(id); refresh(); } }}>{() => <p role="status" className="rounded-xl bg-lime/40 p-3 text-sm">Rendered. Your video is ready below.</p>}</JobView>
      ) : (
        <button className="btn btn-primary w-full" disabled={over} onClick={async () => {
          setErr("");
          if (!(await flush())) { setErr("Your latest edits could not be saved yet, so the render was not started."); return; }
          try { setJob((await api<{ job_id: string }>(`/projects/${id}/render`, { body: { mode } })).job_id); } catch (e) { setErr((e as Error).message); }
        }}>Render {mode} video</button>
      )}
      {output && (
        <div className="text-center">
          <video src={output} controls playsInline className="mx-auto w-full max-w-[240px] rounded-2xl bg-ink" style={{ aspectRatio: "9 / 16" }} aria-label="Last rendered video" />
          <a className="btn btn-ghost mt-2" href={output} download>Download last render</a>
        </div>
      )}
      {versions.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm font-medium">Edit history ({versions.length})</summary>
          <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-sm">
            {versions.map((v) => (
              <li key={v.id} className="flex items-center justify-between rounded-lg bg-line/60 px-3 py-1.5">
                <span>v{v.version} · {v.scenes} scenes · {new Date(v.at).toLocaleTimeString()}</span>
                <button className="underline" onClick={async () => { if (await flush()) { await api(`/projects/${id}/versions/${v.id}/restore`, { body: {} }); await load(id); } }}>Restore</button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
