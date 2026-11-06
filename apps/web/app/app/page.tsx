"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { Me, getMe, logout } from "@/lib/api";

export default function Dashboard() {
  const r = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    getMe().then((m) => (m ? setMe(m) : r.replace("/login"))).catch(() => r.replace("/login"));
  }, [r]);
  if (!me) return <main className="p-10">Loading…</main>;
  const unlimited = me.mode === "self_host";
  return (
    <main className="mx-auto max-w-3xl px-5 py-8">
      <header className="flex items-center justify-between">
        <Logo />
        <button className="btn btn-ghost" onClick={async () => { await logout(); r.push("/"); }}>Sign out</button>
      </header>
      <h1 className="mt-10 text-3xl font-bold">Hi{me.name ? `, ${me.name}` : ""}</h1>
      <div className="card mt-6 p-5">
        <p className="text-sm text-muted">Credits</p>
        <p className="font-mono text-3xl font-bold">{unlimited ? "Unlimited" : me.credits}</p>
        <p className="mt-1 text-xs text-muted">Plan: {me.plan_id}{unlimited ? " (self-hosted)" : ""}</p>
      </div>
      {!me.email_verified && (
        <p className="mt-4 rounded-xl bg-coral/10 px-3 py-2 text-sm">
          Please verify your email. In local mode the link is in the <Link className="underline" href="/dev-mail">dev inbox</Link>.
        </p>
      )}
      <p className="mt-8 text-muted">Video creation arrives in the next phases.</p>
    </main>
  );
}
