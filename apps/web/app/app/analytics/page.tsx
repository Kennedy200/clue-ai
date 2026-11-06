"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type A = { videos: number; by_status: Record<string, number>; by_style: Record<string, number>; minutes_made: number; credits_spent_30d: number; spend_by_day: { date: string; credits: number }[]; posts: { planned: number; published: number } };

export default function Analytics() {
  const [a, setA] = useState<A | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<A>("/analytics").then(setA).catch((e) => setErr(e.message)); }, []);
  if (!a) return <p className="text-muted" aria-busy="true">{err || "Loading…"}</p>;
  const max = Math.max(1, ...a.spend_by_day.map((d) => d.credits));
  const styles = Object.entries(a.by_style).sort((x, y) => y[1] - x[1]);
  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold">Your numbers</h1>
      <p className="mt-1 text-sm text-muted">What you made and spent. Views and watch time live on each platform; Clue AI does not read them.</p>
      <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[["Videos", a.videos], ["Minutes made", a.minutes_made], ["Credits (30 days)", a.credits_spent_30d], ["Posts published", a.posts.published]].map(([k, v]) => (
          <div key={String(k)} className="card p-4"><dt className="text-xs text-muted">{k}</dt><dd className="font-display text-3xl font-bold">{v}</dd></div>
        ))}
      </dl>
      <h2 className="mt-8 text-xl font-semibold">Credits per day</h2>
      {a.spend_by_day.length === 0 ? <p className="mt-2 text-sm text-muted">No spending in the last 30 days.</p> : (
        <ul className="mt-3 space-y-1" aria-label="Credits spent per day">
          {a.spend_by_day.map((d) => <li key={d.date} className="flex items-center gap-2 text-xs"><span className="w-20 shrink-0 text-muted">{d.date.slice(5)}</span><span className="h-3 rounded-full bg-violet" style={{ width: `${(d.credits / max) * 100}%`, minWidth: 6 }} /><span>{d.credits}</span></li>)}
        </ul>
      )}
      <h2 className="mt-8 text-xl font-semibold">By style</h2>
      {styles.length === 0 ? <p className="mt-2 text-sm text-muted">Make a video to see this.</p> : <ul className="mt-2 divide-y divide-line rounded-2xl border border-line bg-card text-sm">{styles.map(([k, v]) => <li key={k} className="flex justify-between p-3"><span>{k.replace("_", " ")}</span><b>{v}</b></li>)}</ul>}
    </div>
  );
}
