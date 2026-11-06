"use client";
import { useState } from "react";
import { AuthShell, Field, FormError } from "@/components/AuthShell";
import { api } from "@/lib/api";

export default function Forgot() {
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      await api("/auth/forgot", { body: { email: String(new FormData(e.currentTarget).get("email")) } });
      setDone(true);
    } catch (x) {
      setErr((x as Error).message);
    }
  }
  return (
    <AuthShell title="Reset your password" subtitle="We will email you a reset link.">
      {done ? (
        <p>
          If that email has an account, a reset link is on its way. In local mode, check the{" "}
          <a className="underline" href="/dev-mail">dev inbox</a>.
        </p>
      ) : (
        <form onSubmit={submit}>
          <FormError msg={err} />
          <Field label="Email" name="email" type="email" required />
          <button className="btn btn-primary w-full">Send link</button>
        </form>
      )}
    </AuthShell>
  );
}
