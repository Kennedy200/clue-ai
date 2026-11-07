"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useMe } from "@/components/AppShell";
import { STYLE_INFO } from "@/components/CreateForm";
import { api } from "@/lib/api";

type Proj = { id: string; title: string; style: string; status: string; created_at: string };
type Quota = { ok: boolean; usage?: number; error?: string };

export default function Dashboard() {
  const { me } = useMe();
  const [projects, setProjects] = useState<Proj[]>([]);
  const [quota, setQuota] = useState<Quota | null>(null);
  useEffect(() => {
    api<Proj[]>("/projects").then((p) => setProjects(p.slice(0, 4))).catch(() => {});
    api<Quota>("/ai/quota").then(setQuota).catch(() => {});
  }, []);
  const unlimited = me.mode === "self_host";
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Hi{me.name ? `, ${me.name}` : ""}</h1>
        <p className="text-muted">What are we making today?</p>
      </div>

      {!me.email_verified && (
        <p className="rounded-xl bg-coral/10 px-3 py-2 text-sm">Please verify your email. In local mode the link is in the <Link className="underline" href="/dev-mail">dev inbox</Link>.</p>
      )}
      {quota && !quota.ok && (
        <p className="rounded-xl bg-lime/40 px-3 py-2 text-sm">AI writing is off: {quota.error} Everything else works. <Link className="underline" href="/setup">Set up AI</Link></p>
      )}

      <section aria-label="Create a video">
        <h2 className="mb-3 text-xl font-semibold">Create a video</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(STYLE_INFO).map(([k, v]) => (
            <Link key={k} href={`/app/create/${k}`} className="card p-4 transition-transform hover:-translate-y-0.5">
              <h3 className="font-semibold">{v.title}</h3><p className="mt-1 text-sm text-muted">{v.blurb}</p>
            </Link>
          ))}
          <Link href="/app/tools/clips" className="card bg-violet p-4 text-white transition-transform hover:-translate-y-0.5" style={{ background: "var(--violet)" }}>
            <h3 className="font-semibold">Auto Clipping</h3><p className="mt-1 text-sm">Long video in, best short clips out.</p>
          </Link>
        </div>
      </section>

      <section aria-label="Credits" className="card flex items-center justify-between p-4">
        <div><p className="text-sm text-muted">Credits</p><p className="font-mono text-3xl font-bold">{unlimited ? "Unlimited" : me.credits}</p></div>
        <p className="max-w-xs text-right text-xs text-muted">Plan: {me.plan_id}{unlimited ? " · self-hosted, no limits" : ""}. You always see the cost before you spend.</p>
      </section>

      <section aria-label="Recent videos">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-xl font-semibold">Recent videos</h2><Link href="/app/projects" className="text-sm underline">See all</Link></div>
        {projects.length === 0 ? <p className="text-muted">Nothing yet. Pick a style above to make your first video.</p> : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {projects.map((p) => (
              <li key={p.id}><Link href={`/app/projects?open=${p.id}`} className="card flex items-center justify-between p-3"><span className="font-medium">{p.title}</span><span className="text-xs text-muted">{p.status}</span></Link></li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
