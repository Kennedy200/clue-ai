"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthShell, FormError } from "@/components/AuthShell";
import { api, getMe } from "@/lib/api";

type Status = { has_key: boolean; has_users: boolean; mode: string };

export default function Setup() {
  const [status, setStatus] = useState<Status | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Status>("/setup/status").then(setStatus).catch((e) => setErr(e.message));
    getMe().then((m) => setIsAdmin(!!m?.is_admin)).catch(() => {});
  }, []);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const key = String(new FormData(e.currentTarget).get("key"));
    setBusy(true); setErr(""); setMsg("");
    try {
      // Open on first run (no users yet); afterwards only the admin endpoint is allowed.
      const path = status?.has_users ? "/admin/key" : "/setup/key";
      await api(path, { body: { key } });
      setMsg("Key verified and saved. AI features are on.");
      setStatus((s) => (s ? { ...s, has_key: true } : s));
    } catch (x) {
      setErr((x as Error).message);
    }
    setBusy(false);
  }

  const locked = status?.has_users && !isAdmin;
  return (
    <AuthShell title="Set up AI" subtitle="Paste your free OpenRouter key once. Everything else runs locally.">
      {status?.has_key && <p className="mb-3 rounded-xl bg-lime/40 px-3 py-2 text-sm">A key is already saved. Paste a new one to replace it.</p>}
      {locked ? (
        <p>Sign in as the admin to change the key. <Link className="underline" href="/login">Sign in</Link></p>
      ) : (
        <form onSubmit={save}>
          <FormError msg={err} />
          {msg && <p role="status" className="mb-3 rounded-xl bg-lime/40 px-3 py-2 text-sm">{msg}</p>}
          <label className="mb-3 block text-sm font-medium">
            OpenRouter API key
            <input className="input mt-1 font-mono" name="key" type="password" autoComplete="off" placeholder="sk-or-v1-…" required />
          </label>
          <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Testing…" : "Test and save key"}</button>
          <p className="mt-3 text-xs text-muted">
            Get a free key at openrouter.ai/keys. It is stored encrypted on this machine. Without a key the app still works for
            everything except AI writing.
          </p>
        </form>
      )}
      <Link href="/signup" className="mt-4 inline-block text-sm underline">Continue to the app</Link>
    </AuthShell>
  );
}
