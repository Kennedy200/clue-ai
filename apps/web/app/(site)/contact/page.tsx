"use client";
import { useState } from "react";
import { FormError } from "@/components/AuthShell";
import { api } from "@/lib/api";

export default function Contact() {
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true); setErr("");
    try {
      await api("/contact", { body: { name: String(f.get("name")), email: String(f.get("email")), message: String(f.get("message")) } });
      setDone(true);
    } catch (x) { setErr((x as Error).message); }
    setBusy(false);
  }
  return (
    <div className="mx-auto max-w-xl px-5 py-14">
      <h1 className="text-4xl font-bold">Contact and support</h1>
      <p className="mt-3 text-muted">Questions, bugs or ideas? Send a message and it goes straight to the team.</p>
      {done ? (
        <p role="status" className="card mt-8 p-5">Thanks. Your message was received.</p>
      ) : (
        <form onSubmit={submit} className="card mt-8 p-5">
          <FormError msg={err} />
          <label className="mb-3 block text-sm font-medium">Name<input className="input mt-1" name="name" required maxLength={120} /></label>
          <label className="mb-3 block text-sm font-medium">Email<input className="input mt-1" name="email" type="email" required /></label>
          <label className="mb-3 block text-sm font-medium">Message<textarea className="input mt-1 py-2" name="message" rows={5} required minLength={5} maxLength={4000} /></label>
          <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Sending…" : "Send message"}</button>
        </form>
      )}
    </div>
  );
}
