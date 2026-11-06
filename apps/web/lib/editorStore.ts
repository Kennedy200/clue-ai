import { create } from "zustand";
import { ApiError, api } from "./api";
import * as ops from "./scene";
import type { Scene, SceneProject } from "./scene";

export type SaveState = "saved" | "dirty" | "saving" | "offline" | "conflict";
const HISTORY_LIMIT = 100;

type Loaded = { id: string; title: string; style: string; status: string; version: number; scene: SceneProject; files: Record<string, string>; output_url: string | null };

type State = {
  id: string; title: string; style: string; status: string; version: number; output: string | null;
  scene: SceneProject | null; files: Record<string, string>;
  selected: number; time: number; playing: boolean;
  past: SceneProject[]; future: SceneProject[];
  save: SaveState; saveError: string;
  load: (id: string) => Promise<void>;
  edit: (fn: (s: SceneProject) => SceneProject, opts?: { merge?: boolean }) => void;
  undo: () => void; redo: () => void;
  select: (i: number) => void; seek: (t: number) => void; play: (on?: boolean) => void;
  addFiles: (f: Record<string, string>) => void;
  flush: () => Promise<boolean>;
  setTitle: (t: string) => void;
};

let saveTimer: ReturnType<typeof setTimeout> | null = null;
let lastEditAt = 0;

export const useEditor = create<State>((set, get) => ({
  id: "", title: "", style: "", status: "", version: 0, output: null, scene: null, files: {},
  selected: 0, time: 0, playing: false, past: [], future: [], save: "saved", saveError: "",

  async load(id) {
    const p = await api<Loaded>(`/projects/${id}`);
    set({ id: p.id, title: p.title, style: p.style, status: p.status, version: p.version, scene: p.scene, files: p.files, output: p.output_url,
      selected: 0, time: 0, playing: false, past: [], future: [], save: "saved", saveError: "" });
  },

  /** Apply an edit. Edits made within 800 ms of each other (typing, dragging a slider) merge into one undo step. */
  edit(fn, opts) {
    const { scene, past } = get();
    if (!scene) return;
    const next = fn(scene);
    if (next === scene) return;
    const now = Date.now();
    const merge = opts?.merge ?? now - lastEditAt < 800;
    lastEditAt = now;
    set({ scene: next, past: merge && past.length ? past : [...past, scene].slice(-HISTORY_LIMIT), future: [], save: "dirty",
      selected: Math.min(get().selected, next.scenes.length - 1) });
    scheduleSave();
  },

  undo() {
    const { past, scene, future } = get();
    if (!past.length || !scene) return;
    const prev = past[past.length - 1];
    set({ scene: prev, past: past.slice(0, -1), future: [scene, ...future], save: "dirty", selected: Math.min(get().selected, prev.scenes.length - 1) });
    lastEditAt = 0;
    scheduleSave();
  },
  redo() {
    const { future, scene, past } = get();
    if (!future.length || !scene) return;
    const [next, ...rest] = future;
    set({ scene: next, future: rest, past: [...past, scene], save: "dirty", selected: Math.min(get().selected, next.scenes.length - 1) });
    lastEditAt = 0;
    scheduleSave();
  },

  select: (i) => set((st) => ({ selected: Math.max(0, Math.min(i, (st.scene?.scenes.length ?? 1) - 1)) })),
  seek: (t) => set({ time: Math.max(0, Math.min(t, get().scene ? ops.total(get().scene!) : 0)) }),
  play: (on) => set((st) => ({ playing: on ?? !st.playing })),
  addFiles: (f) => set((st) => ({ files: { ...st.files, ...f } })),
  setTitle: (title) => { set({ title, save: "dirty" }); scheduleSave(); },

  /** Save now. Returns true when the server has the latest edit. */
  async flush() {
    if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; }
    const { id, scene, version, title, save } = get();
    if (!scene || save === "saved" || save === "conflict") return save === "saved";
    set({ save: "saving" });
    try {
      const r = await api<{ version: number }>(`/projects/${id}/scene`, { method: "PUT", body: { scene, base_version: version, title } });
      const unchanged = get().scene === scene;
      set({ version: r.version, save: unchanged ? "saved" : "dirty", saveError: "" });
      try { localStorage.removeItem(`clue-draft-${id}`); } catch { /* private mode */ }
      if (!unchanged) scheduleSave();
      return unchanged;
    } catch (e) {
      try { localStorage.setItem(`clue-draft-${id}`, JSON.stringify({ version, scene, at: Date.now() })); } catch { /* storage full */ }
      if (e instanceof ApiError && e.status === 409) { set({ save: "conflict", saveError: e.message }); return false; }
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) { set({ save: "dirty", saveError: e.message }); return false; }
      set({ save: "offline", saveError: "You are offline. Your edits are kept on this device and will save when you reconnect." });
      saveTimer = setTimeout(() => void get().flush(), 5000);
      return false;
    }
  },
}));

function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => void useEditor.getState().flush(), 1500);
}

export type { Scene };
