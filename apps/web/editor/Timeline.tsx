"use client";
import { useRef } from "react";
import { useEditor } from "@/lib/editorStore";
import { PALETTES, locate, minDuration, move, patchScene } from "@/lib/scene";

const PPS = 34; // pixels per second
const MIN_W = 76;
const widthOf = (d: number) => Math.max(MIN_W, d * PPS);

/** Scene blocks, proportional to length. Select, drag to reorder, drag the right edge to trim. Keyboard and buttons work too. */
export function Timeline() {
  const { scene, selected, time, select, seek, edit } = useEditor();
  const dragFrom = useRef<number | null>(null);
  const trim = useRef<{ i: number; x: number; d: number } | null>(null);
  if (!scene) return null;

  const lefts: number[] = [];
  let x = 0;
  for (const s of scene.scenes) { lefts.push(x); x += widthOf(s.duration) + 6; }
  const loc = locate(scene, time);
  const headX = lefts[loc.index] + (loc.local / scene.scenes[loc.index].duration) * widthOf(scene.scenes[loc.index].duration);

  const startsAt = (i: number) => scene.scenes.slice(0, i).reduce((a, s) => a + s.duration, 0);

  return (
    <div className="overflow-x-auto pb-2" role="listbox" aria-label="Timeline of scenes" aria-orientation="horizontal" tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") { e.preventDefault(); select(selected + 1); seek(startsAt(Math.min(selected + 1, scene.scenes.length - 1))); }
        if (e.key === "ArrowLeft") { e.preventDefault(); select(selected - 1); seek(startsAt(Math.max(selected - 1, 0))); }
      }}>
      <div className="relative flex h-[84px] gap-[6px]" style={{ width: x }}>
        {scene.scenes.map((s, i) => {
          const v = s.visual;
          const [c0, c1] = PALETTES[v.seed % PALETTES.length];
          return (
            <div key={s.id} role="option" aria-selected={i === selected} aria-label={`Scene ${i + 1}: ${s.text.slice(0, 40)}, ${s.duration.toFixed(1)} seconds`}
              draggable onDragStart={() => (dragFrom.current = i)} onDragOver={(e) => e.preventDefault()}
              onDrop={() => { if (dragFrom.current !== null) edit((sc) => move(sc, dragFrom.current!, i), { merge: false }); select(i); dragFrom.current = null; }}
              onClick={(e) => { select(i); const r = e.currentTarget.getBoundingClientRect(); seek(startsAt(i) + ((e.clientX - r.left) / r.width) * s.duration); }}
              className={`relative shrink-0 cursor-pointer overflow-hidden rounded-xl border-2 p-2 text-left text-xs text-white ${i === selected ? "border-lime" : "border-transparent"}`}
              style={{ width: widthOf(s.duration), background: `linear-gradient(135deg, #${c0}, #${c1})` }}>
              <span className="font-mono font-bold">{i + 1}</span>
              <span className="ml-1 text-[10px] opacity-80">{s.duration.toFixed(1)}s{s.transition === "fade" ? " · fade" : ""}</span>
              <p className="mt-1 line-clamp-3 break-words leading-tight">{s.text}</p>
              {i === selected && (
                <span role="slider" aria-label="Trim scene length" aria-valuemin={minDuration(s)} aria-valuemax={30} aria-valuenow={s.duration} tabIndex={0}
                  className="absolute inset-y-0 right-0 flex w-5 cursor-ew-resize touch-none items-center justify-center bg-lime/90 text-ink"
                  onPointerDown={(e) => { e.stopPropagation(); (e.target as HTMLElement).setPointerCapture(e.pointerId); trim.current = { i, x: e.clientX, d: s.duration }; }}
                  onPointerMove={(e) => { const t = trim.current; if (!t) return; const d = Math.min(30, Math.max(minDuration(s), t.d + (e.clientX - t.x) / PPS)); edit((sc) => patchScene(sc, t.i, { duration: Math.round(d * 10) / 10 }), { merge: true }); }}
                  onPointerUp={() => (trim.current = null)}
                  onKeyDown={(e) => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.stopPropagation(); e.preventDefault(); const d = Math.min(30, Math.max(minDuration(s), s.duration + (e.key === "ArrowRight" ? 0.1 : -0.1))); edit((sc) => patchScene(sc, i, { duration: Math.round(d * 10) / 10 }), { merge: true }); } }}>⋮</span>
              )}
            </div>
          );
        })}
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-coral" style={{ left: headX }} aria-hidden><span className="absolute -top-1 -left-1 h-2.5 w-2.5 rounded-full bg-coral" /></div>
      </div>
    </div>
  );
}
