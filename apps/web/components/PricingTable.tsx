"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

export type PlanRow = { id: string; name: string; price_ngn_month: number; price_usd_month: number; monthly_credits: number; features: Record<string, unknown> };

const BULLETS: Record<string, string[]> = {
  free: ["Fast mode", "Watermark on hosted plans", "Core tools"],
  starter: ["Fast mode up to 60 s", "35+ voices", "Auto captions", "YouTube Shorts publishing"],
  creator: ["Everything in Starter", "Pro and Cinematic modes", "Brand kits", "Priority render queue"],
  business: ["Everything in Creator", "Team workspace and roles", "Bulk creation (CSV)", "Top render priority"],
};

export function PricingTable({ plans }: { plans: PlanRow[] }) {
  const [annual, setAnnual] = useState(true);
  const [cur, setCur] = useState<"NGN" | "USD">("NGN");
  useEffect(() => {
    // Naira first for visitors in Nigeria, otherwise USD; always switchable.
    const loc = navigator.language || "";
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    setCur(loc.endsWith("-NG") || tz === "Africa/Lagos" ? "NGN" : "USD");
  }, []);
  const fmt = (p: PlanRow) => {
    const m = cur === "NGN" ? p.price_ngn_month : p.price_usd_month / 100;
    const v = annual ? m / 2 : m;
    if (v === 0) return "Free";
    return cur === "NGN" ? `₦${Math.round(v).toLocaleString("en-NG")}` : `$${v.toFixed(v % 1 ? 2 : 0)}`;
  };
  return (
    <div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <div role="group" aria-label="Billing period" className="inline-flex rounded-2xl border border-line bg-card p-1">
          <button className={`btn ${annual ? "btn-primary" : ""}`} aria-pressed={annual} onClick={() => setAnnual(true)}>Annual · 50% off</button>
          <button className={`btn ${!annual ? "btn-primary" : ""}`} aria-pressed={!annual} onClick={() => setAnnual(false)}>Monthly</button>
        </div>
        <div role="group" aria-label="Currency" className="inline-flex rounded-2xl border border-line bg-card p-1">
          {(["NGN", "USD"] as const).map((c) => (
            <button key={c} className={`btn ${cur === c ? "btn-primary" : ""}`} aria-pressed={cur === c} onClick={() => setCur(c)}>{c === "NGN" ? "₦ NGN" : "$ USD"}</button>
          ))}
        </div>
      </div>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {plans.map((p) => (
          <section key={p.id} className={`card flex flex-col p-5 ${p.id === "creator" ? "ring-2 ring-violet" : ""}`}>
            <h2 className="text-xl font-bold">{p.name}</h2>
            <p className="mt-3 font-display text-4xl font-bold">{fmt(p)}<span className="text-sm font-normal text-muted">{p.price_ngn_month ? "/mo" : ""}</span></p>
            {annual && p.price_ngn_month > 0 && <p className="text-xs text-muted">billed yearly</p>}
            <p className="mt-2 text-sm font-medium">{p.monthly_credits} credits / month</p>
            <ul className="mt-4 flex-1 space-y-2 text-sm text-muted">
              {(BULLETS[p.id] ?? []).map((b) => <li key={b}>✓ {b}</li>)}
            </ul>
            <Link href="/signup" className={`btn mt-5 ${p.id === "creator" ? "btn-primary" : "btn-ghost"}`}>{p.price_ngn_month ? `Choose ${p.name}` : "Start free"}</Link>
          </section>
        ))}
      </div>
      <p className="mt-6 text-center text-xs text-muted">
        Self-hosted installs are free with unlimited credits. On this build payments are simulated by the built-in billing engine; a payment gateway plugin is needed to charge real money.
      </p>
    </div>
  );
}
