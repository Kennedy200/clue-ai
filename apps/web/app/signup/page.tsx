"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthShell, Field, FormError } from "@/components/AuthShell";
import { signup } from "@/lib/api";

export default function Signup() {
  const r = useRouter();
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [ref, setRef] = useState("");
  useEffect(() => { setRef((new URLSearchParams(window.location.search).get("ref") || "").slice(0, 16)); }, []);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setErr("");
    try {
      await signup(String(f.get("email")), String(f.get("password")), String(f.get("name")), String(f.get("ref") || ""));
      r.push("/app");
    } catch (x) {
      setErr((x as Error).message);
      setBusy(false);
    }
  }
  return (
    <AuthShell title="Create your account" subtitle="Free to start. No camera needed.">
      <form onSubmit={submit}>
        <FormError msg={err} />
        <Field label="Name" name="name" autoComplete="name" />
        <Field label="Email" name="email" type="email" autoComplete="email" required />
        <Field label="Password (8+ characters)" name="password" type="password" minLength={8} autoComplete="new-password" required />
        <Field label="Referral code (optional)" name="ref" value={ref} onChange={(e) => setRef(e.target.value)} />
        <button className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-sm text-muted">
        Already have an account? <Link href="/login" className="underline">Sign in</Link>
      </p>
    </AuthShell>
  );
}
