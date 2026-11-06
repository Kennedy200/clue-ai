"use client";
import { useCallback, useEffect, useState } from "react";
import { useMe } from "@/components/AppShell";
import type { PlanRow } from "@/components/PricingTable";
import { api } from "@/lib/api";

type Sub = { status: string; interval: string; currency: string; period_end: string; cancel_at_period_end: boolean; pending_plan_id: string | null; next_retry_at: string | null };
type Bill = { plan_id: string; plan_name: string; credits: number; mode: string; subscription: Sub | null; topups: { id: string; credits: number; ngn: number; usd: number }[] };
type Inv = { id: string; number: string; description: string; display: string; status: string; date: string };
type Ref = { code: string; link: string; friends: number; earned: number; reward: number; mode: string };
type Led = { balance: number; entries: { date: string; delta: number; reason: string; kind: string }[] };

const day = (s: string) => new Date(s + "Z").toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

export default function Billing() {
  const { refresh } = useMe();
  const [bill, setBill] = useState<Bill | null>(null);
  const [plans, setPlans] = useState<PlanRow[]>([]);
  const [inv, setInv] = useState<Inv[]>([]);
  const [ref, setRef] = useState<Ref | null>(null);
  const [led, setLed] = useState<Led | null>(null);
  const [cur, setCur] = useState<"NGN" | "USD">("NGN");
  const [yearly, setYearly] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    const [b, p, i, r, l] = await Promise.all([api<Bill>("/billing"), api<PlanRow[]>("/plans"), api<Inv[]>("/billing/invoices"), api<Ref>("/referrals"), api<Led>("/billing/ledger")]);
    setBill(b); setPlans(p); setInv(i); setRef(r); setLed(l); refresh();
  }, [refresh]);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [load]);

  async function act(path: string, body?: unknown) {
    setErr(""); setMsg(""); setBusy(true);
    try { const r = await api<{ message: string }>(path, { method: "POST", body: body ?? {} }); setMsg(r.message); await load(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  const price = (p: PlanRow) => {
    const m = cur === "NGN" ? p.price_ngn_month : p.price_usd_month / 100;
    const t = yearly ? m * 6 : m;
    return cur === "NGN" ? `₦${t.toLocaleString("en-NG")}` : `$${t.toFixed(2)}`;
  };
  if (!bill) return <p className="text-muted" aria-busy="true">{err || "Loading…"}</p>;
  const sub = bill.subscription;

  return (
    <div className="max-w-3xl">
      <h1 className="text-3xl font-bold">Billing and credits</h1>
      <p className="mt-1 text-sm text-muted">Payments here are simulated by the built-in billing engine. No real money moves until a payment gateway plugin is installed.</p>
      <div aria-live="polite">
        {msg && <p role="status" className="mt-3 rounded-xl bg-lime/40 p-3 text-sm">{msg}</p>}
        {err && <p role="alert" className="mt-3 rounded-xl bg-coral/10 p-3 text-sm text-coral">{err}</p>}
      </div>

      <section className="card mt-5 p-5" aria-label="Current plan">
        <p className="text-sm text-muted">Current plan</p>
        <p className="font-display text-2xl font-bold">{bill.plan_name} <span className="ml-2 font-mono text-base">{bill.mode === "self_host" ? "∞" : bill.credits} credits</span></p>
        {sub && sub.status !== "cancelled" && <p className="mt-1 text-sm">{sub.cancel_at_period_end ? "Ends" : "Renews"} on {day(sub.period_end)}{sub.pending_plan_id ? ` · moving to ${sub.pending_plan_id} then` : ""}{sub.status === "past_due" ? " · payment failed, we will retry" : ""}</p>}
        {sub && sub.status !== "cancelled" && !sub.cancel_at_period_end && <button className="btn btn-ghost mt-3" disabled={busy} onClick={() => { if (confirm("Cancel your plan? You keep it until the period ends and you keep your credits.")) act("/billing/cancel"); }}>Cancel plan</button>}
      </section>

      <div className="mt-6 flex flex-wrap gap-2">
        <div role="group" aria-label="Billing period" className="inline-flex rounded-2xl border border-line bg-card p-1">
          <button className={`btn ${!yearly ? "btn-primary" : ""}`} aria-pressed={!yearly} onClick={() => setYearly(false)}>Monthly</button>
          <button className={`btn ${yearly ? "btn-primary" : ""}`} aria-pressed={yearly} onClick={() => setYearly(true)}>Yearly · 50% off</button>
        </div>
        <div role="group" aria-label="Currency" className="inline-flex rounded-2xl border border-line bg-card p-1">
          {(["NGN", "USD"] as const).map((c) => <button key={c} className={`btn ${cur === c ? "btn-primary" : ""}`} aria-pressed={cur === c} onClick={() => setCur(c)}>{c}</button>)}
        </div>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {plans.filter((p) => p.price_ngn_month > 0).map((p) => (
          <section key={p.id} className="card p-4" aria-label={`${p.name} plan`}>
            <h2 className="font-bold">{p.name}</h2>
            <p className="mt-1 font-display text-2xl font-bold">{price(p)}<span className="text-xs font-normal text-muted">{yearly ? "/yr" : "/mo"}</span></p>
            <p className="text-sm text-muted">{yearly ? p.monthly_credits * 12 : p.monthly_credits} credits</p>
            <button className="btn btn-primary mt-3 w-full" disabled={busy || bill.plan_id === p.id && sub?.interval === (yearly ? "year" : "month") && !sub?.cancel_at_period_end}
              onClick={() => act("/billing/subscribe", { plan_id: p.id, interval: yearly ? "year" : "month", currency: cur })}>
              {bill.plan_id === p.id && sub?.interval === (yearly ? "year" : "month") ? "Current plan" : `Choose ${p.name}`}
            </button>
          </section>
        ))}
      </div>

      <h2 className="mt-8 text-xl font-semibold">Top up credits</h2>
      <p className="text-sm text-muted">One-off packs. They never expire.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {bill.topups.map((t) => (
          <button key={t.id} className="card p-4 text-left disabled:opacity-60" disabled={busy}
            onClick={() => act("/billing/topup", { pack_id: t.id, currency: cur, idempotency_key: crypto.randomUUID().slice(0, 24) })}>
            <span className="font-display text-2xl font-bold">{t.credits}</span> <span className="text-sm text-muted">credits</span>
            <span className="mt-1 block text-sm font-medium">{cur === "NGN" ? `₦${(t.ngn / 100).toLocaleString("en-NG")}` : `$${(t.usd / 100).toFixed(2)}`}</span>
          </button>
        ))}
      </div>

      {ref && (
        <section className="card mt-8 p-5" aria-label="Invite friends">
          <h2 className="text-xl font-semibold">Invite friends</h2>
          <p className="mt-1 text-sm text-muted">{ref.reward ? `You and your friend each get ${ref.reward} credits when they sign up with your link.` : "Share your link. (Referral credits are off on self-hosted installs because credits are unlimited.)"}</p>
          <div className="mt-3 flex gap-2">
            <input readOnly aria-label="Your invite link" className="input min-w-0 flex-1 font-mono text-xs" value={ref.link} onFocus={(e) => e.currentTarget.select()} />
            <button className="btn btn-ghost" onClick={async () => { await navigator.clipboard?.writeText(ref.link).catch(() => {}); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>{copied ? "Copied" : "Copy"}</button>
          </div>
          <p className="mt-2 text-sm">{ref.friends} friend{ref.friends === 1 ? "" : "s"} joined · {ref.earned} credits earned</p>
        </section>
      )}

      <h2 className="mt-8 text-xl font-semibold">Invoices</h2>
      {inv.length === 0 ? <p className="mt-2 text-sm text-muted">No invoices yet.</p> : (
        <ul className="mt-2 divide-y divide-line rounded-2xl border border-line bg-card">
          {inv.map((i) => (
            <li key={i.id} className="flex items-center justify-between gap-3 p-3 text-sm">
              <div><b>{i.number}</b> <span className={`ml-1 rounded-full px-2 py-0.5 text-xs ${i.status === "paid" ? "bg-lime text-ink" : "bg-coral/20 text-coral"}`}>{i.status}</span><br /><span className="text-muted">{i.description} · {day(i.date)}</span></div>
              <div className="text-right"><b>{i.display}</b><br /><a className="underline" href={`/api/billing/invoices/${i.id}/html`} target="_blank" rel="noreferrer">View</a></div>
            </li>
          ))}
        </ul>
      )}

      <h2 className="mt-8 text-xl font-semibold">Credit history</h2>
      <ul className="mt-2 divide-y divide-line rounded-2xl border border-line bg-card text-sm">
        {led?.entries.slice(0, 20).map((e, i) => (
          <li key={i} className="flex justify-between gap-3 p-3"><span>{e.reason || e.kind} <span className="text-muted">· {day(e.date)}</span></span><b className={e.delta < 0 ? "text-coral" : ""}>{e.delta > 0 ? "+" : ""}{e.delta}</b></li>
        ))}
      </ul>
    </div>
  );
}
