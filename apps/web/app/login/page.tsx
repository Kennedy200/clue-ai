"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell, Field, FormError } from "@/components/AuthShell";
import { login } from "@/lib/api";

export default function Login() {
  const r = useRouter();
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setErr("");
    try {
      await login(String(f.get("email")), String(f.get("password")));
      r.push("/app");
    } catch (x) {
      setErr((x as Error).message);
      setBusy(false);
    }
  }
  return (
    <AuthShell title="Welcome back" subtitle="Sign in to keep creating.">
      <form onSubmit={submit}>
        <FormError msg={err} />
        <Field label="Email" name="email" type="email" autoComplete="email" required />
        <Field label="Password" name="password" type="password" autoComplete="current-password" required />
        <button className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="mt-4 text-sm text-muted">
        <Link href="/forgot" className="underline">Forgot password?</Link> · <Link href="/signup" className="underline">Create account</Link>
      </p>
    </AuthShell>
  );
}
