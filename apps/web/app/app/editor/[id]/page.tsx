"use client";
import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { useEditor } from "@/lib/editorStore";
import { CaptionsPanel, ExportPanel, MusicPanel, ScenePanel, VoicePanel } from "@/editor/Panels";
import { Player, Transport } from "@/editor/Player";
import { Timeline } from "@/editor/Timeline";
import { duplicate, locate, remove } from "@/lib/scene";

const TABS = [["scene", "Scene"], ["captions", "Captions"], ["voice", "Voice"], ["music", "Music"], ["export", "Export"]] as const;
type Tab = (typeof TABS)[number][0];

/** Desktop: fixed. Phone: as big as fits above the timeline, smaller while the bottom sheet is open. */
function usePlayerWidth(sheetOpen: boolean) {
  const [w, setW] = useState(300);
  useEffect(() => {
    const calc = () => setW(window.innerWidth >= 768 ? 300 : Math.max(96, Math.min(window.innerWidth - 40, Math.floor(window.innerHeight * (sheetOpen ? 0.27 : 0.46) * (9 / 16)))));
    calc();
    window.addEventListener("resize", calc);
    return () => window.removeEventListener("resize", calc);
  }, [sheetOpen]);
  return w;
}

function SaveChip() {
  const { save, saveError, flush } = useEditor();
  const map = { saved: ["Saved", "bg-lime text-ink"], dirty: ["Unsaved", "bg-line"], saving: ["Saving…", "bg-line"], offline: ["Offline, kept on this device", "bg-coral/20 text-coral"], conflict: ["Conflict", "bg-coral text-white"] } as const;
  const [label, cls] = map[save];
  return (
    <button className={`rounded-full px-3 py-1 text-xs font-medium ${cls}`} onClick={() => flush()} title={saveError || "Click to save now"} role="status" aria-live="polite">{label}</button>
  );
}

export default function Editor({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { scene, title, setTitle, load, undo, redo, past, future, save, saveError, selected, time, status } = useEditor();
  const [tab, setTab] = useState<Tab>("scene");
  const [err, setErr] = useState("");
  const [sheet, setSheet] = useState(false);
  const [draft, setDraft] = useState(false);
  const width = usePlayerWidth(sheet);

  useEffect(() => {
    useEditor.setState({ scene: null });
    load(id).then(() => {
      try { setDraft(!!localStorage.getItem(`clue-draft-${id}`)); } catch { /* ignore */ }
    }).catch((e) => setErr(e.message));
    return () => useEditor.getState().play(false);
  }, [id, load]);

  // leaving with unsaved edits: try to save, and warn if the browser can still see them
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => { const s = useEditor.getState().save; if (s !== "saved") { void useEditor.getState().flush(); e.preventDefault(); } };
    window.addEventListener("beforeunload", h);
    return () => { window.removeEventListener("beforeunload", h); void useEditor.getState().flush(); };
  }, []);

  const onKey = useCallback((e: KeyboardEvent) => {
    const t = e.target as HTMLElement;
    const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) && (t as HTMLInputElement).type !== "range" && (t as HTMLInputElement).type !== "color";
    const st = useEditor.getState();
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? st.redo() : st.undo(); return; }
    if (mod && e.key.toLowerCase() === "y") { e.preventDefault(); st.redo(); return; }
    if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); void st.flush(); return; }
    if (typing || !st.scene) return;
    if (e.key === " ") { e.preventDefault(); st.play(); }
    else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); st.edit((s) => remove(s, st.selected), { merge: false }); }
    else if (e.key.toLowerCase() === "d" && !mod) { st.edit((s) => duplicate(s, st.selected), { merge: false }); st.select(st.selected + 1); }
  }, []);
  useEffect(() => { window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, [onKey]);

  if (err) return <p role="alert" className="rounded-xl bg-coral/10 p-4 text-coral">{err} <Link href="/app/projects" className="underline">Back to videos</Link></p>;
  if (!scene) return <p className="text-muted" aria-busy="true">Loading the editor…</p>;
  const locked = status === "rendering";
  const panel = { scene: <ScenePanel />, captions: <CaptionsPanel />, voice: <VoicePanel />, music: <MusicPanel />, export: <ExportPanel /> }[tab];

  return (
    <div className={`${sheet ? "pb-[52vh]" : "pb-24"} md:pb-0`}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Link href="/app/projects" className="btn btn-ghost !min-h-10 text-sm" aria-label="Back to your videos">←</Link>
        <input aria-label="Video title" className="input !min-h-10 min-w-0 flex-1 font-semibold" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
        <button className="btn btn-ghost !min-h-10 !px-3" onClick={undo} disabled={!past.length} aria-label="Undo" title="Undo (Ctrl+Z)">↶</button>
        <button className="btn btn-ghost !min-h-10 !px-3" onClick={redo} disabled={!future.length} aria-label="Redo" title="Redo (Ctrl+Y)">↷</button>
        <SaveChip />
      </div>

      {save === "conflict" && (
        <div role="alert" className="mb-3 rounded-xl bg-coral/10 p-3 text-sm text-coral">
          {saveError} <button className="underline" onClick={() => load(id)}>Reload the latest version</button> (your unsaved edits on this screen will be replaced).
        </div>
      )}
      {save === "offline" && <p role="alert" className="mb-3 rounded-xl bg-coral/10 p-3 text-sm text-coral">{saveError}</p>}
      {save !== "conflict" && save !== "offline" && saveError && <p role="alert" className="mb-3 rounded-xl bg-coral/10 p-3 text-sm text-coral">{saveError}</p>}
      {locked && <p role="status" className="mb-3 rounded-xl bg-lime/40 p-3 text-sm">This video is rendering. You can look around, but saving edits is paused until it finishes.</p>}
      {draft && save === "saved" && (
        <p className="mb-3 rounded-xl bg-line p-3 text-sm">
          Unsaved changes from a previous session were found on this device.{" "}
          <button className="underline" onClick={() => { try { const d = JSON.parse(localStorage.getItem(`clue-draft-${id}`) || "{}"); if (d.scene) useEditor.getState().edit(() => d.scene, { merge: false }); localStorage.removeItem(`clue-draft-${id}`); } catch { /* ignore */ } setDraft(false); }}>Restore them</button>{" "}
          or <button className="underline" onClick={() => { try { localStorage.removeItem(`clue-draft-${id}`); } catch { /* ignore */ } setDraft(false); }}>discard</button>.
        </p>
      )}

      <div className="grid gap-5 md:grid-cols-[320px_1fr]">
        <div className="md:sticky md:top-20 md:self-start">
          <Player width={width} />
          <Transport />
          <div className="mt-3"><Timeline /></div>
          <p className="mt-1 hidden text-xs text-muted md:block">Shortcuts: Space play · Ctrl+Z undo · Ctrl+Y redo · ←/→ scenes · D duplicate · Delete remove · Ctrl+S save</p>
          <p className="mt-1 text-xs text-muted">Scene {locate(scene, time).index + 1} of {scene.scenes.length} · selected {selected + 1}</p>
        </div>

        <section aria-label="Editing panel" className={`fixed inset-x-0 bottom-0 z-20 overflow-hidden rounded-t-3xl border-t border-line bg-card shadow-[0_-8px_30px_rgba(14,11,31,.15)] md:static md:z-auto md:rounded-2xl md:border md:shadow-none ${sheet ? "max-h-[50vh]" : "max-h-14"} md:max-h-none`}>
          <button className="flex w-full justify-center py-2 md:hidden" onClick={() => setSheet(!sheet)} aria-expanded={sheet} aria-label={sheet ? "Collapse editing panel" : "Expand editing panel"}><span className="h-1.5 w-12 rounded-full bg-line" /></button>
          <div role="tablist" aria-label="Editor sections" className="flex gap-1 overflow-x-auto px-3 pb-2 md:pt-3">
            {TABS.map(([k, t]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => { setTab(k); setSheet(true); }} className={`shrink-0 rounded-xl px-3 py-2 text-sm font-medium ${tab === k ? "bg-violet text-white" : "bg-line"}`}>{t}</button>
            ))}
          </div>
          <div role="tabpanel" className="max-h-[calc(50vh-6rem)] overflow-y-auto px-4 pb-6 md:max-h-none md:overflow-visible">{panel}</div>
        </section>
      </div>
    </div>
  );
}
