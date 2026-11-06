"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getMe } from "@/lib/api";

type Plugin = { name: string; kind: string; title?: string; description?: string; valid: boolean; error?: string; setting?: string; enabled?: boolean };

export default function Admin() {
  const r = useRouter();
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [quota, setQuota] = useState("");
  const [err, setErr] = useState("");
  const load = () => api<Plugin[]>("/plugins").then(setPlugins);
  useEffect(() => {
    getMe().then((m) => {
      if (!m?.is_admin) return r.replace("/login");
      load();
      api<{ ok: boolean; usage?: number; error?: string }>("/ai/quota").then((q) => setQuota(q.ok ? `OpenRouter usage: ${q.usage ?? 0}` : q.error ?? ""));
    });
  }, [r]);

  async function toggle(p: Plugin, enabled: boolean) {
    setErr("");
    setPlugins((all) => all.map((x) => (x.kind === p.kind && x.name === p.name ? { ...x, enabled } : x))); // show the change at once
    try { await api(`/admin/plugins/${p.kind}/${p.name}`, { body: { enabled } }); } catch (e) { setErr((e as Error).message); await load(); } // revert on failure
  }
  return (
    <main className="mx-auto max-w-3xl px-5 py-8">
      <h1 className="text-3xl font-bold">Admin</h1>
      <p className="mt-2 text-sm text-muted">{quota}</p>
      <h2 className="mt-8 text-xl font-semibold">Plugins</h2>
      {err && <p role="alert" className="mt-2 text-sm text-coral">{err}</p>}
      {plugins.length === 0 && <p className="mt-2 text-muted">No plugins installed yet. See docs/PLUGINS.md.</p>}
      {plugins.map((p) => (
        <div key={`${p.kind}/${p.name}`} className="card mt-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <b>{p.title ?? p.name}</b> <span className="ml-1 rounded-full bg-line px-2 py-0.5 text-xs">{p.kind}</span>
              {p.description && <p className="mt-1 text-sm text-muted">{p.description}</p>}
              {!p.valid && <p className="text-sm text-coral">Invalid: {p.error}</p>}
            </div>
            {p.setting && (
              <label className="flex shrink-0 items-center gap-2 text-sm font-medium">
                <input type="checkbox" role="switch" aria-label={`Turn ${p.title ?? p.name} on or off`} checked={!!p.enabled} onChange={(e) => toggle(p, e.target.checked)} className="h-5 w-5" />
                {p.enabled ? "On" : "Off"}
              </label>
            )}
          </div>
        </div>
      ))}
    </main>
  );
}
