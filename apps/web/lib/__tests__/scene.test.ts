import { beforeEach, describe, expect, it, vi } from "vitest";
import * as ops from "../scene";
import type { Scene, SceneProject } from "../scene";

const vis = { kind: "procedural" as const, path: null, seed: 0, attribution: null, start: 0, has_audio: false, audio_volume: null };
const sc = (id: string, text: string, duration: number, words = text.split(" ").map((w, i) => ({ w, start: i * 0.5, end: i * 0.5 + 0.4 }))): Scene => ({
  id, text, audio_path: `u/${id}.wav`, duration, words, visual: vis, visual2: null, on_screen_text: null, badge: null, transition: "cut",
});
const project = (): SceneProject => ({
  width: 1080, height: 1920, fps: 30, mode: "fast", layout: "full", watermark: null, music_path: null, music_volume: 0.12,
  captions: { ...(ops.CAPTION_PRESETS["bold-highlight"] as object), name: "bold-highlight", font: "Arial", position: "lower" } as SceneProject["captions"],
  scenes: [sc("a", "one two three four", 3), sc("b", "five six", 2), sc("c", "seven eight nine", 4)],
});

describe("scene operations", () => {
  it("locates the scene and local time", () => {
    const p = project();
    expect(ops.locate(p, 0)).toEqual({ index: 0, local: 0 });
    expect(ops.locate(p, 3.5)).toEqual({ index: 1, local: 0.5 });
    expect(ops.locate(p, 99).index).toBe(2);
    expect(ops.total(p)).toBe(9);
    expect(ops.starts(p)).toEqual([0, 3, 5]);
  });

  it("moves, deletes (never the last scene) and duplicates", () => {
    const p = project();
    expect(ops.move(p, 0, 2).scenes.map((s) => s.id)).toEqual(["b", "c", "a"]);
    expect(ops.move(p, 1, 1)).toBe(p);
    expect(ops.move(p, 0, 9)).toBe(p);
    expect(ops.remove(p, 1).scenes.map((s) => s.id)).toEqual(["a", "c"]);
    const one = { ...p, scenes: [p.scenes[0]] };
    expect(ops.remove(one, 0)).toBe(one);
    const d = ops.duplicate(p, 0);
    expect(d.scenes).toHaveLength(4);
    expect(d.scenes[1].id).not.toBe("a");
    expect(d.scenes[1].words).not.toBe(p.scenes[0].words);
  });

  it("finds a sensible split point and splits text", () => {
    const s = project().scenes[0];
    expect(ops.splitPoint(s, 0.9)).toBe(2);
    expect(ops.splitPoint(s, 0)).toBe(1);
    expect(ops.splitPoint(s, 99)).toBe(3);
    expect(ops.splitPoint(sc("x", "single", 2), 1)).toBeNull();
    expect(ops.splitText("one two three four", 2)).toEqual(["one two", "three four"]);
  });

  it("enforces a minimum duration so the voice is not cut off", () => {
    expect(ops.minDuration(project().scenes[0])).toBeCloseTo(1.5 + 0.4 + 0.15, 5);
    expect(ops.minDuration({ ...project().scenes[0], words: [] })).toBe(1);
  });

  it("builds caption chunks with the active word", () => {
    const s = project().scenes[0];
    expect(ops.captionAt(s, 0.1, 2)).toEqual({ words: ["one", "two"], active: 0 });
    expect(ops.captionAt(s, 1.1, 2)).toEqual({ words: ["three", "four"], active: 0 });
    expect(ops.captionAt(s, 1.6, 2)).toEqual({ words: ["three", "four"], active: 1 });
    expect(ops.captionAt(s, 2.9, 2)).toBeNull();
  });

  it("edits one word without touching timing and never mutates its input", () => {
    const p = project();
    const n = ops.editWord(p, 0, 1, "TWO!");
    expect(n.scenes[0].words[1]).toEqual({ ...p.scenes[0].words[1], w: "TWO!" });
    expect(p.scenes[0].words[1].w).toBe("two");
    expect(ops.editWord(p, 5, 0, "x")).toBe(p);
  });
});

describe("editor store: undo, redo, merging, autosave", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.useFakeTimers();
  });

  async function boot(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
    const store = (await import("../editorStore")).useEditor;
    const calls: { url: string; body: unknown }[] = [];
    vi.stubGlobal("fetch", async (url: string, init: RequestInit = {}) => {
      calls.push({ url, body: init.body ? JSON.parse(String(init.body)) : null });
      return handler(url, init);
    });
    store.setState({ id: "P1", title: "T", version: 0, scene: project(), files: {}, past: [], future: [], save: "saved", selected: 0 });
    return { store, calls };
  }
  const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

  it("undo and redo walk back and forth, and a new edit clears redo", async () => {
    const { store } = await boot(() => reply({ version: 1 }));
    store.getState().edit((s) => ops.remove(s, 0), { merge: false });
    store.getState().edit((s) => ops.move(s, 0, 1), { merge: false });
    expect(store.getState().scene!.scenes.map((x) => x.id)).toEqual(["c", "b"]);
    store.getState().undo();
    expect(store.getState().scene!.scenes.map((x) => x.id)).toEqual(["b", "c"]);
    store.getState().undo();
    expect(store.getState().scene!.scenes).toHaveLength(3);
    store.getState().redo();
    expect(store.getState().scene!.scenes).toHaveLength(2);
    store.getState().edit((s) => ops.remove(s, 0), { merge: false });
    expect(store.getState().future).toHaveLength(0);
  });

  it("rapid edits merge into a single undo step", async () => {
    const { store } = await boot(() => reply({ version: 1 }));
    store.getState().edit((s) => ops.patchScene(s, 0, { text: "a" }), { merge: false });
    for (const t of ["ab", "abc", "abcd"]) store.getState().edit((s) => ops.patchScene(s, 0, { text: t }));
    expect(store.getState().past).toHaveLength(1);
    store.getState().undo();
    expect(store.getState().scene!.scenes[0].text).toBe("one two three four");
  });

  it("autosaves after a pause using the current version, then reports saved", async () => {
    const { store, calls } = await boot(() => reply({ version: 1 }));
    store.getState().edit((s) => ops.patchScene(s, 0, { transition: "fade" }), { merge: false });
    expect(store.getState().save).toBe("dirty");
    await vi.advanceTimersByTimeAsync(1600);
    const put = calls.find((c) => c.url.includes("/scene"))!;
    expect((put.body as { base_version: number }).base_version).toBe(0);
    expect(store.getState().save).toBe("saved");
    expect(store.getState().version).toBe(1);
  });

  it("a 409 stops autosave and reports a conflict rather than overwriting", async () => {
    const { store, calls } = await boot(() => reply({ detail: "This project changed elsewhere" }, 409));
    store.getState().edit((s) => ops.remove(s, 2), { merge: false });
    await vi.advanceTimersByTimeAsync(1600);
    expect(store.getState().save).toBe("conflict");
    const n = calls.length;
    await vi.advanceTimersByTimeAsync(20000);
    expect(calls.length).toBe(n);
  });

  it("offline edits stay dirty, are kept on the device, and save when the connection returns", async () => {
    let online = false;
    const { store } = await boot(() => {
      if (!online) throw new TypeError("Failed to fetch");
      return reply({ version: 1 });
    });
    const memo: Record<string, string> = {};
    vi.stubGlobal("localStorage", { setItem: (k: string, v: string) => (memo[k] = v), removeItem: (k: string) => delete memo[k], getItem: (k: string) => memo[k] ?? null });
    store.getState().edit((s) => ops.remove(s, 0), { merge: false });
    await vi.advanceTimersByTimeAsync(1600);
    expect(store.getState().save).toBe("offline");
    expect(memo["clue-draft-P1"]).toContain("scenes");
    online = true;
    await vi.advanceTimersByTimeAsync(5200);
    expect(store.getState().save).toBe("saved");
    expect(memo["clue-draft-P1"]).toBeUndefined();
  });
});
