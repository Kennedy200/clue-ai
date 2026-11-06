"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { api } from "@/lib/api";

function Inner() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState("Verifying…");
  useEffect(() => {
    api("/auth/verify", { body: { token } })
      .then(() => setState("Email verified. You are all set."))
      .catch((e) => setState(e.message));
  }, [token]);
  return (
    <AuthShell title="Email verification">
      <p>{state}</p>
      <Link href="/app" className="btn btn-primary mt-4">Go to app</Link>
    </AuthShell>
  );
}
export default function Verify() {
  return (
    <Suspense>
      <Inner />
    </Suspense>
  );
}
