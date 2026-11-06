"use client";
import { useEffect, useState } from "react";

const SCORES = [92, 87, 81];

/** Looping CSS/SVG demo: a wide video is scanned, three vertical clips pop out with ticking scores. No video file. */
export function HeroDemo() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setTick(30); return; }
    const id = setInterval(() => setTick((t) => (t + 1) % 40), 160);
    return () => clearInterval(id);
  }, []);
  const phase = tick < 15 ? "scan" : "clips";
  const progress = Math.min(1, tick / 15);
  return (
    <div className="card relative mx-auto w-full max-w-md overflow-hidden p-4" role="img" aria-label="Animation: a long video is scanned and three scored vertical clips appear">
      <div className="relative h-28 rounded-xl bg-ink">
        <div className="absolute inset-y-0 w-1 bg-lime" style={{ left: `${progress * 100}%`, transition: "left .1s linear" }} />
        <div className="absolute left-3 top-3 font-mono text-xs text-paper/70">podcast-episode.mp4 · 42:10</div>
        <svg className="absolute bottom-0 h-10 w-full" viewBox="0 0 200 20" preserveAspectRatio="none" aria-hidden>
          <polyline fill="none" stroke="#6C4DFF" strokeWidth="1.5" points="0,12 15,8 30,14 45,5 60,13 75,9 90,16 105,4 120,12 135,7 150,14 165,6 180,11 200,9" />
        </svg>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {SCORES.map((s, i) => {
          const shown = phase === "clips" ? Math.min(s, Math.round(((tick - 15 - i * 3) / 10) * s)) : 0;
          return (
            <div key={s} className="aspect-[9/16] rounded-xl bg-violet/90 p-2 text-paper transition-all duration-300"
              style={{ opacity: phase === "clips" && tick > 15 + i * 3 ? 1 : 0.15, transform: phase === "clips" && tick > 15 + i * 3 ? "none" : "translateY(10px)" }}>
              <div className="font-mono text-[10px] opacity-80">Clue Score</div>
              <div className="font-mono text-2xl font-bold text-lime">{Math.max(0, shown)}</div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-center text-xs text-muted">Illustration of the Auto Clipping flow.</p>
    </div>
  );
}
