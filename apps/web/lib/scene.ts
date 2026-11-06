/** Scene JSON types (mirror apps/api/clue/render/scene.py) and pure, unit-tested operations on them. */

export type Word = { w: string; start: number; end: number };
export type Visual = { kind: "procedural" | "image" | "video"; path: string | null; seed: number; attribution: string | null; start: number; has_audio: boolean; audio_volume: number | null };
export type Scene = {
  id: string; text: string; audio_path: string | null; duration: number; words: Word[]; visual: Visual; visual2: Visual | null;
  on_screen_text: string | null; badge: string | null; transition: "cut" | "fade";
};
export type CaptionStyle = {
  name: string; font: string; size: number; color: string; highlight: string; outline: string; position: "middle" | "lower";
  words_per_chunk: number; box: boolean; uppercase: boolean; outline_width: number; animate: "none" | "pop"; highlight_mode: "colour" | "none";
};
export type SceneProject = {
  width: number; height: number; fps: number; mode: "fast" | "pro" | "cinematic"; layout: "full" | "split";
  scenes: Scene[]; captions: CaptionStyle; watermark: string | null; music_path: string | null; music_volume: number;
};

export const PALETTES: [string, string][] = [["6C4DFF", "0E0B1F"], ["0E0B1F", "C8FF3D"], ["FF5C7A", "6C4DFF"], ["0E0B1F", "6C4DFF"], ["3B2BB5", "FF5C7A"], ["101030", "00A896"], ["C8FF3D", "6C4DFF"], ["2A2548", "FF5C7A"]];

export const CAPTION_PRESETS: Record<string, { label: string } & Partial<CaptionStyle>> = {
  "bold-highlight": { label: "Bold highlight", color: "FFFFFF", highlight: "C8FF3D", outline: "000000", outline_width: 7, box: false, uppercase: false, words_per_chunk: 4, size: 84, animate: "none", highlight_mode: "colour" },
  classic: { label: "Classic", color: "FFFFFF", highlight: "FFFFFF", outline: "000000", outline_width: 6, box: false, uppercase: false, highlight_mode: "none", words_per_chunk: 5, size: 84, animate: "none" },
  "yellow-box": { label: "Yellow box", color: "111111", highlight: "FFFFFF", outline: "FFD400", box: true, outline_width: 14, words_per_chunk: 3, uppercase: false, size: 84, animate: "none", highlight_mode: "colour" },
  "lime-box": { label: "Lime box", color: "0E0B1F", highlight: "FFFFFF", outline: "C8FF3D", box: true, outline_width: 14, words_per_chunk: 3, uppercase: true, size: 84, animate: "none", highlight_mode: "colour" },
  karaoke: { label: "Karaoke", color: "FFFFFF", highlight: "FF5C7A", outline: "0E0B1F", outline_width: 8, words_per_chunk: 5, box: false, uppercase: false, size: 84, animate: "none", highlight_mode: "colour" },
  neon: { label: "Neon", color: "E8F9FF", highlight: "00E5FF", outline: "1B0B4D", outline_width: 9, uppercase: true, box: false, words_per_chunk: 4, size: 84, animate: "none", highlight_mode: "colour" },
  "pop-single": { label: "One word pop", color: "FFFFFF", highlight: "C8FF3D", outline: "000000", outline_width: 9, words_per_chunk: 1, size: 130, uppercase: true, animate: "pop", position: "middle", box: false, highlight_mode: "colour" },
  minimal: { label: "Minimal", color: "FFFFFF", highlight: "FFFFFF", outline: "000000", outline_width: 3, size: 62, highlight_mode: "none", words_per_chunk: 6, box: false, uppercase: false, animate: "none" },
  "violet-box": { label: "Violet box", color: "FFFFFF", highlight: "C8FF3D", outline: "6C4DFF", box: true, outline_width: 14, words_per_chunk: 3, uppercase: false, size: 84, animate: "none", highlight_mode: "colour" },
  "heavy-outline": { label: "Heavy outline", color: "FFFFFF", highlight: "FFD400", outline: "000000", outline_width: 12, size: 96, words_per_chunk: 3, uppercase: true, box: false, animate: "none", highlight_mode: "colour" },
};

export const total = (s: SceneProject) => s.scenes.reduce((a, x) => a + x.duration, 0);
export const starts = (s: SceneProject) => { let t = 0; return s.scenes.map((x) => { const r = t; t += x.duration; return r; }); };

/** Which scene is playing at time t, and how far into it. */
export function locate(s: SceneProject, t: number): { index: number; local: number } {
  let acc = 0;
  for (let i = 0; i < s.scenes.length; i++) {
    if (t < acc + s.scenes[i].duration || i === s.scenes.length - 1) return { index: i, local: Math.min(Math.max(0, t - acc), s.scenes[i].duration) };
    acc += s.scenes[i].duration;
  }
  return { index: 0, local: 0 };
}

/** Shortest a scene may be: long enough that its voice is not cut off. */
export const minDuration = (sc: Scene) => Math.max(1, (sc.words.length ? sc.words[sc.words.length - 1].end : 0) + 0.15);

let counter = 0;
export const newId = () => `s${Date.now().toString(36)}${(counter++).toString(36)}`;

export function move(s: SceneProject, from: number, to: number): SceneProject {
  if (from === to || from < 0 || to < 0 || from >= s.scenes.length || to >= s.scenes.length) return s;
  const scenes = [...s.scenes];
  const [x] = scenes.splice(from, 1);
  scenes.splice(to, 0, x);
  return { ...s, scenes };
}

export function remove(s: SceneProject, i: number): SceneProject {
  if (s.scenes.length <= 1 || i < 0 || i >= s.scenes.length) return s; // a video always keeps at least one scene
  return { ...s, scenes: s.scenes.filter((_, j) => j !== i) };
}

export function duplicate(s: SceneProject, i: number): SceneProject {
  const sc = s.scenes[i];
  if (!sc) return s;
  const scenes = [...s.scenes];
  scenes.splice(i + 1, 0, { ...structuredClone(sc), id: newId() });
  return { ...s, scenes };
}

export function patchScene(s: SceneProject, i: number, patch: Partial<Scene>): SceneProject {
  return { ...s, scenes: s.scenes.map((x, j) => (j === i ? { ...x, ...patch } : x)) };
}

/** Where to cut a scene's text so the first part ends at (or just after) local time t. Returns word index (1..n-1) or null. */
export function splitPoint(sc: Scene, local: number): number | null {
  const n = sc.text.trim().split(/\s+/).length;
  if (n < 2) return null;
  if (sc.words.length >= 2) {
    const k = sc.words.findIndex((w) => w.end >= local);
    return Math.min(n - 1, Math.max(1, (k < 0 ? sc.words.length : k) + 1));
  }
  return Math.min(n - 1, Math.max(1, Math.round((n * local) / Math.max(sc.duration, 0.1))));
}

export function splitText(text: string, at: number): [string, string] {
  const words = text.trim().split(/\s+/);
  return [words.slice(0, at).join(" "), words.slice(at).join(" ")];
}

/** Caption chunk shown at local time t within a scene: the words in view and which one is being spoken. */
export function captionAt(sc: Scene, local: number, perChunk: number): { words: string[]; active: number } | null {
  const ws = sc.words;
  if (!ws.length) return null;
  let k = ws.findIndex((w) => local >= w.start && local < w.end);
  if (k < 0) k = ws.findIndex((w) => w.start > local) - 1;
  if (k < 0 || (local > ws[ws.length - 1].end + 0.3)) return null;
  const first = Math.floor(k / perChunk) * perChunk;
  return { words: ws.slice(first, first + perChunk).map((w) => w.w), active: k - first };
}

/** Edit a single word's text, keeping its timing (typo fixes). */
export function editWord(s: SceneProject, si: number, wi: number, text: string): SceneProject {
  const sc = s.scenes[si];
  if (!sc || !sc.words[wi]) return s;
  const words = sc.words.map((w, j) => (j === wi ? { ...w, w: text } : w));
  return patchScene(s, si, { words });
}
