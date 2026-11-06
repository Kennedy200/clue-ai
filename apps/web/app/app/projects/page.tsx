"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { VideoResult } from "@/components/JobView";
import { api } from "@/lib/api";
import { fmtTime } from "@/lib/jobs";

type Proj = { id: string; title: string; style: string; status: string; duration_ms: number | null; created_at: string };

function Inner() {
  const [rows, setRows] = useState<Proj[] | null>(null);
  const [open, setOpen] = useState<string | null>(useSearchParams().get("open"));
  useEffect(() => { api<Proj[]>("/projects").then(setRows).catch(() => setRows([])); }, []);
  if (!rows) return <p className="text-muted" aria-busy="true">Loading…</p>;
  return (
    <div>
      <h1 className="mb-4 text-3xl font-bold">Your videos</h1>
      {rows.length === 0 && <p className="text-muted">No videos yet. <Link className="underline" href="/app/create/text_story">Make your first one</Link>.</p>}
      <ul className="space-y-3">
        {rows.map((p) => (
          <li key={p.id} className="card p-4">
            <button className="flex w-full items-center justify-between text-left" onClick={() => setOpen(open === p.id ? null : p.id)} aria-expanded={open === p.id}>
              <span><b>{p.title}</b><span className="ml-2 text-xs text-muted">{p.style.replace("_", " ")} · {new Date(p.created_at).toLocaleDateString()}</span></span>
              <span className="font-mono text-xs">{p.status === "done" && p.duration_ms ? fmtTime(p.duration_ms / 1000) : p.status}</span>
            </button>
            {open === p.id && p.status === "done" && <div className="mt-4"><VideoResult projectId={p.id} /></div>}
            {open === p.id && p.status !== "done" && <p className="mt-3 text-sm text-muted">This video is not ready ({p.status}).</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
export default function Projects() { return <Suspense><Inner /></Suspense>; }
