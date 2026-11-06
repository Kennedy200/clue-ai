"use client";
import { useEffect, useRef } from "react";
import { useEditor } from "@/lib/editorStore";
import { PALETTES, captionAt, locate, starts, total } from "@/lib/scene";
import type { Scene, Visual } from "@/lib/scene";

const hex = (c: string) => `#${c}`;

function Layer({ v, scene, local, files, height, muted }: { v: Visual; scene: Scene; local: number; files: Record<string, string>; height: string; muted: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);
  const playing = useEditor((s) => s.playing);
  const src = v.path ? files[v.path] : undefined;
  useEffect(() => {
    const el = ref.current;
    if (!el || v.kind !== "video") return;
    const want = v.start + local;
    const len = el.duration || 0;
    const target = len > 1 ? want % len : want;
    if (Math.abs(el.currentTime - target) > 0.4) el.currentTime = target;
    if (playing) el.play().catch(() => {}); else el.pause();
    el.volume = v.audio_volume ?? 0;
  }); // runs every frame on purpose: keeps the clip in step with the clock
  const style = { height, width: "100%", position: "relative" as const, overflow: "hidden" as const };
  if (v.kind === "image" && src)
    return <div style={style}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={src} alt="" draggable={false} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1 + (0.18 * local) / Math.max(scene.duration, 0.1)})` }} /></div>;
  if (v.kind === "video" && src)
    return <div style={style}><video ref={ref} src={src} muted={muted || !v.audio_volume} playsInline preload="auto" style={{ width: "100%", height: "100%", objectFit: "cover" }} /></div>;
  const [a, b] = PALETTES[v.seed % PALETTES.length];
  return <div style={{ ...style, background: `linear-gradient(135deg, ${hex(a)}, ${hex(b)})` }} />;
}

/** Plays the Scene JSON in the browser: visuals, voice, captions, badges. Same data the FFmpeg renderer reads. */
export function Player({ width }: { width: number }) {
  const { scene, files, time, playing, seek, play } = useEditor();
  const audio = useRef<HTMLAudioElement>(null);
  const raf = useRef(0);
  const last = useRef(0);
  const stateRef = useRef({ time, scene });
  stateRef.current = { time, scene };

  // the clock
  useEffect(() => {
    if (!playing) return;
    last.current = performance.now();
    const tick = (now: number) => {
      const { scene: sc, time: t } = stateRef.current;
      if (!sc) return;
      const nt = t + (now - last.current) / 1000;
      last.current = now;
      if (nt >= total(sc)) { play(false); seek(0); return; }
      seek(nt);
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, play, seek]);

  const loc = scene ? locate(scene, time) : { index: 0, local: 0 };
  const sc = scene?.scenes[loc.index];
  const src = sc?.audio_path ? files[sc.audio_path] : undefined;

  // the voice: one element, re-pointed at each scene
  useEffect(() => {
    const el = audio.current;
    if (!el) return;
    if (!src) { el.pause(); return; }
    if (el.dataset.src !== src) {
      el.src = src;
      el.dataset.src = src;
      el.currentTime = loc.local;
    }
    if (Math.abs(el.currentTime - loc.local) > 0.35) el.currentTime = loc.local; // after a seek or a drift
    if (playing) el.play().catch(() => {}); else el.pause();
  });

  if (!scene || !sc) return null;
  const cap = captionAt(sc, loc.local, scene.captions.words_per_chunk);
  const k = width / 1080;
  const c = scene.captions;
  const split = scene.layout === "split";
  const half = `${100 / (split ? 2 : 1)}%`;
  return (
    <div className="relative mx-auto select-none overflow-hidden rounded-2xl bg-ink" style={{ width, height: width * (16 / 9) }} role="img" aria-label={`Preview, scene ${loc.index + 1} of ${scene.scenes.length}`}>
      <Layer v={sc.visual} scene={sc} local={loc.local} files={files} height={half} muted={false} />
      {split && <Layer v={sc.visual2 ?? { kind: "procedural", path: null, seed: sc.visual.seed + 3, attribution: null, start: 0, has_audio: false, audio_volume: null }} scene={sc} local={loc.local} files={files} height={half} muted />}
      {sc.on_screen_text && <div className="absolute inset-x-0 text-center font-bold text-white" style={{ top: 170 * k, padding: `0 ${70 * k}px` }}><span style={{ background: "rgba(0,0,0,.65)", padding: `${6 * k}px ${14 * k}px`, fontSize: 64 * k, boxDecorationBreak: "clone" }}>{sc.on_screen_text}</span></div>}
      {sc.badge && <div className="absolute font-black" style={{ left: 60 * k, top: 150 * k, fontSize: 190 * k, color: hex(c.highlight), WebkitTextStroke: `${6 * k}px #000`, paintOrder: "stroke fill", lineHeight: 1 }}>{sc.badge}</div>}
      {cap && (
        <div className="absolute inset-x-0 text-center font-extrabold" style={{ [c.position === "middle" || split ? "top" : "bottom"]: c.position === "middle" || split ? "50%" : 560 * k, transform: c.position === "middle" || split ? "translateY(-50%)" : undefined, padding: `0 ${80 * k}px`, fontSize: c.size * k, lineHeight: 1.15, fontFamily: "Arial, sans-serif" }}>
          <span style={{ background: c.box ? hex(c.outline) : undefined, padding: c.box ? `${4 * k}px ${12 * k}px` : undefined, boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone", textShadow: c.box ? undefined : `0 0 ${c.outline_width * k}px ${hex(c.outline)}, 0 0 ${c.outline_width * k}px ${hex(c.outline)}, 0 0 ${c.outline_width * k}px ${hex(c.outline)}` }}>
            {cap.words.map((w, i) => (
              <span key={i} style={{ color: hex(i === cap.active && c.highlight_mode === "colour" ? c.highlight : c.color) }}>{(c.uppercase ? w.toUpperCase() : w) + (i < cap.words.length - 1 ? " " : "")}</span>
            ))}
          </span>
        </div>
      )}
      <audio ref={audio} preload="auto" />
    </div>
  );
}

export function Transport() {
  const { scene, time, playing, play, seek } = useEditor();
  if (!scene) return null;
  const t = total(scene);
  const fmt = (x: number) => `${Math.floor(x / 60)}:${String(Math.floor(x % 60)).padStart(2, "0")}`;
  return (
    <div className="mt-3 flex items-center gap-3">
      <button className="btn btn-primary !min-h-11 !w-11 !px-0 text-lg" onClick={() => play()} aria-label={playing ? "Pause" : "Play"}>{playing ? "❚❚" : "▶"}</button>
      <input type="range" aria-label="Seek" className="h-2 flex-1" min={0} max={t} step={0.05} value={Math.min(time, t)} onChange={(e) => seek(Number(e.target.value))} />
      <span className="w-20 text-right font-mono text-xs text-muted">{fmt(time)} / {fmt(t)}</span>
    </div>
  );
}

export { starts };
