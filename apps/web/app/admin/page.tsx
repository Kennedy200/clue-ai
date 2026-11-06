"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getMe } from "@/lib/api";

type Plugin = { name: string; kind: string; title?: string; valid: boolean; error?: string };

export default function Admin() {
  const r = useRouter();
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [quota, setQuota] = useState("");
  useEffect(() => {
    getMe().then((m) => {
      if (!m?.is_admin) return r.replace("/login");
      api<Plugin[]>("/plugins").then(setPlugins);
      api<{ ok: boolean; usage?: number; error?: string }>("/ai/quota").then((q) => setQuota(q.ok ? `OpenRouter usage: ${q.usage ?? 0}` : q.error ?? ""));
    });
  }, [r]);
  return (
    <main className="mx-auto max-w-3xl px-5 py-8">
      <h1 className="text-3xl font-bold">Admin</h1>
      <p className="mt-2 text-sm text-muted">{quota}</p>
      <h2 className="mt-8 text-xl font-semibold">Plugins</h2>
      {plugins.length === 0 && <p className="mt-2 text-muted">No plugins installed yet. See docs/PLUGINS.md.</p>}
      {plugins.map((p) => (
        <div key={`${p.kind}/${p.name}`} className="card mt-3 p-3">
          <b>{p.title ?? p.name}</b> <span className="text-xs text-muted">{p.kind}</span>
          {!p.valid && <p className="text-sm text-coral">Invalid: {p.error}</p>}
        </div>
      ))}
    </main>
  );
}
