"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Job, trackJob } from "@/lib/jobs";
import { useMe } from "./AppShell";

/** Live progress for a job, then the result. `children` receives the finished job. */
export function JobView({ jobId, children, onDone }: { jobId: string; children?: (j: Job) => React.ReactNode; onDone?: (j: Job) => void }) {
  const [job, setJob] = useState<Job | null>(null);
  const { refresh } = useMe();
  useEffect(() => {
    return trackJob(jobId, (j) => {
      setJob(j);
      if (j.status === "done" || j.status === "failed" || j.status === "cancelled") { refresh(); onDone?.(j); }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);
  if (!job) return <p className="text-muted" aria-busy="true">Starting…</p>;
  if (job.status === "failed")
    return <p role="alert" className="rounded-xl bg-coral/10 p-4 text-coral">Something went wrong: {job.error ?? "unknown error"}. Any credits were returned to you.</p>;
  if (job.status === "cancelled") return <p className="rounded-xl bg-line p-4">Cancelled. Your credits were returned.</p>;
  if (job.status === "done") return <>{children?.(job)}</>;
  return (
    <div role="status" aria-live="polite" className="card p-5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{job.status === "queued" ? "Waiting in line…" : job.stage || "Working…"}</span>
        <span className="font-mono">{job.progress}%</span>
      </div>
      <div className="mt-3 h-3 overflow-hidden rounded-full bg-line" aria-hidden>
        <div className="h-full rounded-full bg-violet transition-all duration-500" style={{ width: `${Math.max(3, job.progress)}%` }} />
      </div>
      <button className="btn btn-ghost mt-4 !min-h-9 text-sm" onClick={() => api(`/jobs/${job.id}/cancel`, { body: {} })}>Cancel</button>
    </div>
  );
}

export function useSignedUrl(path: string | null) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!path) return;
    api<{ url: string }>(`/projects/${path}/download-url`).then((r) => setUrl(r.url)).catch(() => setUrl(null));
  }, [path]);
  return url;
}

export function VideoResult({ projectId }: { projectId: string }) {
  const url = useSignedUrl(projectId);
  if (!url) return <p className="text-muted">Preparing your video…</p>;
  return (
    <div className="mx-auto max-w-xs">
      <video src={url} controls playsInline className="w-full rounded-2xl bg-ink" style={{ aspectRatio: "9 / 16" }} />
      <a href={url} download className="btn btn-primary mt-4 w-full">Download MP4</a>
    </div>
  );
}
