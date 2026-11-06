/** Job progress (SSE with polling fallback) and resumable chunked uploads. */
import { api, ApiError, csrfToken } from "./api";

export type Job = {
  id: string; type: string; status: "queued" | "running" | "done" | "failed" | "cancelled";
  progress: number; stage: string; error: string | null; result: Record<string, unknown> | null;
};

/** Follow a job until it finishes. Returns a stop function. Falls back to polling if SSE drops. */
export function trackJob(id: string, rawUpdate: (j: Job) => void): () => void {
  let stopped = false;
  const onUpdate = (j: Job) => {
    if (stopped) return; // ignore late events after the job finished
    if (j.status === "done" || j.status === "failed" || j.status === "cancelled") stopped = true;
    rawUpdate(j);
  };
  let es: EventSource | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  const finished = (j: Job) => j.status === "done" || j.status === "failed" || j.status === "cancelled";

  const poll = async () => {
    if (stopped) return;
    try {
      const j = await api<Job>(`/jobs/${id}`);
      onUpdate(j);
      if (finished(j)) return;
    } catch { /* offline: keep trying */ }
    timer = setTimeout(poll, 2500);
  };

  // Heartbeat: streams can stall silently behind proxies or on flaky mobile data. If nothing has arrived for 6 s, ask directly.
  let last = Date.now();
  const heartbeat = setInterval(async () => {
    if (stopped || Date.now() - last < 6000) return;
    try { onUpdate(await api<Job>(`/jobs/${id}`)); last = Date.now(); } catch { /* offline: try again next tick */ }
  }, 3000);

  try {
    es = new EventSource(`/api/jobs/${id}/events`);
    es.onmessage = (e) => {
      last = Date.now();
      const j = JSON.parse(e.data) as Job;
      onUpdate(j);
      if (finished(j)) { es?.close(); }
    };
    es.onerror = () => { es?.close(); es = null; if (!stopped) poll(); };
  } catch { poll(); }

  return () => { stopped = true; clearInterval(heartbeat); es?.close(); if (timer) clearTimeout(timer); };
}

export type Asset = {
  id: string; kind: "video" | "image" | "audio"; name: string; path: string; duration: number | null;
  width: number | null; height: number | null; has_audio: boolean; size: number; provider: string; attribution: string | null;
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Upload a file in chunks. Each chunk retries with backoff; a dropped connection resumes from the server's offset. */
export async function uploadFile(file: File, onProgress: (pct: number) => void, signal?: { cancelled: boolean }): Promise<Asset> {
  const init = await api<{ id: string; chunk_size: number }>("/uploads/init", { body: { name: file.name, size: file.size } });
  let offset = 0;
  const chunk = Math.min(init.chunk_size, 2 * 1024 * 1024); // smaller chunks survive flaky mobile data
  while (offset < file.size) {
    if (signal?.cancelled) throw new ApiError(0, "Upload cancelled.");
    const end = Math.min(file.size, offset + chunk);
    let ok = false;
    for (let attempt = 0; attempt < 6 && !ok; attempt++) {
      try {
        const r = await fetch(`/api/uploads/${init.id}?offset=${offset}`, {
          method: "PUT", body: file.slice(offset, end), headers: { "x-csrf-token": csrfToken() }, credentials: "same-origin",
        });
        if (r.ok) { offset = (await r.json()).offset; ok = true; }
        else if (r.status === 409) { offset = (await api<{ offset: number }>(`/uploads/${init.id}`)).offset; ok = true; } // resume point
        else throw new ApiError(r.status, ((await r.json().catch(() => ({}))) as { detail?: string }).detail || "Upload failed.");
      } catch (e) {
        if (e instanceof ApiError && e.status >= 400 && e.status < 500) throw e;
        await sleep(Math.min(8000, 800 * 2 ** attempt)); // offline or server hiccup: wait and retry
      }
    }
    if (!ok) throw new ApiError(0, "The connection keeps dropping. Your upload is saved; try again to resume.");
    onProgress(Math.round((offset / file.size) * 100));
  }
  return api<Asset>(`/uploads/${init.id}/finish`, { method: "POST", body: {} });
}

export const fmtBytes = (n: number) => (n > 1e9 ? `${(n / 1e9).toFixed(1)} GB` : n > 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1e3))} KB`);
export const fmtTime = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
