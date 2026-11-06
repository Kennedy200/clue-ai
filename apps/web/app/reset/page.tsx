"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthShell, Field, FormError } from "@/components/AuthShell";
import { api } from "@/lib/api";

function Inner() {
  const token = useSearchParams().get("token") ?? "";
  const r = useRouter();
  const [err, setErr] = useState("");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      await api("/auth/reset", { body: { token, password: String(new FormData(e.currentTarget).get("password")) } });
      r.push("/login");
    } catch (x) {
      setErr((x as Error).message);
    }
  }
  return (
    <AuthShell title="Choose a new password">
      <form onSubmit={submit}>
        <FormError msg={err} />
        <Field label="New password" name="password" type="password" minLength={8} required />
        <button className="btn btn-primary w-full">Save password</button>
      </form>
    </AuthShell>
  );
}
export default function Reset() {
  return (
    <Suspense>
      <Inner />
    </Suspense>
  );
}
