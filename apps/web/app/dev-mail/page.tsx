"use client";
import { useEffect, useState } from "react";

type Mail = { id: string; to: string; subject: string; body: string; at: string };

export default function DevMail() {
  const [mails, setMails] = useState<Mail[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    fetch("/api/dev-mail")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setMails)
      .catch(() => setErr("The dev inbox is only available in self-host mode."));
  }, []);
  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <h1 className="text-2xl font-bold">Dev inbox</h1>
      <p className="text-sm text-muted">Every email the app sends in local mode lands here.</p>
      {err && <p className="mt-4">{err}</p>}
      {mails?.length === 0 && <p className="mt-4">No emails yet.</p>}
      {mails?.map((m) => (
        <article key={m.id} className="card mt-4 p-4">
          <p className="text-xs text-muted">To {m.to} · {m.at}</p>
          <h2 className="font-semibold">{m.subject}</h2>
          <pre className="mt-2 whitespace-pre-wrap break-all text-sm">{m.body}</pre>
        </article>
      ))}
    </main>
  );
}
