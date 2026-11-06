"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, csrfToken, getMe } from "@/lib/api";

type Plugin = { name: string; kind: string; title?: string; description?: string; valid: boolean; error?: string; setting?: string; enabled?: boolean };
type Dash = { users: number; new_users_7d: number; paid_subscribers: number; videos_30d: number; revenue_30d_minor: Record<string, number>; jobs: Record<string, number>; credits_in_circulation: number;
  llm: { calls_30d: number; usd_30d: number; usd_per_video: number | null; by_feature: Record<string, { calls: number; usd: number; failed: number }> } };
type UserRow = { id: string; email: string; name: string; plan_id: string; credits: number; is_admin: boolean; is_suspended: boolean };
type PlanRow = { id: string; name: string; price_ngn_month: number; price_usd_month: number; monthly_credits: number };
type AuditRow = { at: string; actor: string; action: string; detail: Record<string, unknown> };
type ImportRes = { ok: boolean; applied: boolean; errors: { sheet: string; row: number; error: string }[]; summary: { plans: number; grants: number; credits_total: number } };
const TABS = ["Overview", "Users", "Plans", "Excel", "Integrations", "Audit"] as const;

export default function Admin() {
  const r = useRouter();
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [quota, setQuota] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [dash, setDash] = useState<Dash | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [q, setQ] = useState("");
  const [plans, setPlans] = useState<PlanRow[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [imp, setImp] = useState<{ bytes: ArrayBuffer; res: ImportRes } | null>(null);
  const [yt, setYt] = useState({ client_id: "", client_secret: "" });
  const [key, setKey] = useState("");

  const loadPlugins = () => api<Plugin[]>("/plugins").then(setPlugins);
  const loadUsers = useCallback((s = "") => api<UserRow[]>(`/admin/users?q=${encodeURIComponent(s)}`).then(setUsers), []);
  useEffect(() => {
    getMe().then((m) => {
      if (!m?.is_admin) return r.replace("/login");
      loadPlugins();
      api<{ ok: boolean; usage?: number; error?: string }>("/ai/quota").then((x) => setQuota(x.ok ? `OpenRouter usage: ${x.usage ?? 0}` : x.error ?? ""));
      api<Dash>("/admin/dashboard").then(setDash).catch((e) => setErr(e.message));
    });
  }, [r]);
  useEffect(() => {
    if (tab === "Users") loadUsers(q).catch((e) => setErr(e.message));
    if (tab === "Plans") api<PlanRow[]>("/admin/plans").then(setPlans).catch((e) => setErr(e.message));
    if (tab === "Audit") api<AuditRow[]>("/admin/audit").then(setAudit).catch((e) => setErr(e.message));
  }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  async function act(fn: () => Promise<unknown>, ok = "") {
    setErr(""); setMsg("");
    try { await fn(); if (ok) setMsg(ok); } catch (e) { setErr((e as Error).message); }
  }
  async function toggle(p: Plugin, enabled: boolean) {
    setErr("");
    setPlugins((all) => all.map((x) => (x.kind === p.kind && x.name === p.name ? { ...x, enabled } : x))); // show the change at once
    try { await api(`/admin/plugins/${p.kind}/${p.name}`, { body: { enabled } }); } catch (e) { setErr((e as Error).message); await loadPlugins(); } // revert on failure
  }
  async function sendXlsx(bytes: ArrayBuffer, apply: boolean) {
    const resp = await fetch(`/api/admin/import.xlsx?apply=${apply}`, { method: "POST", body: bytes, headers: { "x-csrf-token": csrfToken() } });
    const data = await resp.json();
    if (!resp.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Import failed.");
    setImp({ bytes, res: data });
    if (apply && data.applied) { setMsg("Import applied."); api<PlanRow[]>("/admin/plans").then(setPlans); }
  }
  const money = (m: Record<string, number>) => Object.entries(m).map(([c, v]) => (c === "NGN" ? `₦${(v / 100).toLocaleString("en-NG")}` : `$${(v / 100).toFixed(2)}`)).join(" + ") || "none yet";

  return (
    <main className="mx-auto max-w-4xl px-5 py-8">
      <h1 className="text-3xl font-bold">Admin</h1>
      <p className="mt-2 text-sm text-muted">{quota}</p>
      <div role="tablist" aria-label="Admin sections" className="mt-4 flex gap-1 overflow-x-auto">
        {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`shrink-0 rounded-xl px-3 py-2 text-sm font-medium ${tab === t ? "bg-violet text-white" : "bg-line"}`}>{t}</button>)}
      </div>
      <div aria-live="polite">
        {msg && <p role="status" className="mt-3 rounded-xl bg-lime/40 p-3 text-sm">{msg}</p>}
        {err && <p role="alert" className="mt-3 rounded-xl bg-coral/10 p-3 text-sm text-coral">{err}</p>}
      </div>

      {tab === "Overview" && (
        <section aria-label="Overview">
          {dash && (
            <>
              <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[["Users", dash.users], ["New (7 days)", dash.new_users_7d], ["Paid plans", dash.paid_subscribers], ["Videos (30 days)", dash.videos_30d]].map(([k, v]) => <div key={String(k)} className="card p-3"><dt className="text-xs text-muted">{k}</dt><dd className="font-display text-2xl font-bold">{v}</dd></div>)}
              </dl>
              <div className="card mt-3 p-4 text-sm">
                <p><b>Revenue, 30 days (simulated):</b> {money(dash.revenue_30d_minor)}</p>
                <p className="mt-1"><b>AI cost, 30 days:</b> ${dash.llm.usd_30d} over {dash.llm.calls_30d} calls{dash.llm.usd_per_video != null && <> · about ${dash.llm.usd_per_video} per finished video</>}</p>
                <p className="mt-1"><b>Jobs:</b> {Object.entries(dash.jobs).map(([k, v]) => `${k} ${v}`).join(" · ") || "none"} · <b>Credits in circulation:</b> {dash.credits_in_circulation}</p>
                {Object.keys(dash.llm.by_feature).length > 0 && (
                  <table className="mt-3 w-full text-left"><caption className="sr-only">AI cost by feature</caption><thead><tr><th>Feature</th><th>Calls</th><th>USD</th><th>Failed</th></tr></thead>
                    <tbody>{Object.entries(dash.llm.by_feature).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v.calls}</td><td>{v.usd}</td><td>{v.failed}</td></tr>)}</tbody></table>
                )}
              </div>
            </>
          )}
          <h2 className="mt-8 text-xl font-semibold">Plugins</h2>
          {plugins.length === 0 && <p className="mt-2 text-muted">No plugins installed yet. See docs/PLUGINS.md.</p>}
          {plugins.map((p) => (
            <div key={`${p.kind}/${p.name}`} className="card mt-3 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <b>{p.title ?? p.name}</b> <span className="ml-1 rounded-full bg-line px-2 py-0.5 text-xs">{p.kind}</span>
                  {p.description && <p className="mt-1 text-sm text-muted">{p.description}</p>}
                  {!p.valid && <p className="text-sm text-coral">Invalid: {p.error}</p>}
                </div>
                {p.setting && (
                  <label className="flex shrink-0 items-center gap-2 text-sm font-medium">
                    <input type="checkbox" role="switch" aria-label={`Turn ${p.title ?? p.name} on or off`} checked={!!p.enabled} onChange={(e) => toggle(p, e.target.checked)} className="h-5 w-5" />
                    {p.enabled ? "On" : "Off"}
                  </label>
                )}
              </div>
            </div>
          ))}
        </section>
      )}

      {tab === "Users" && (
        <section aria-label="Users" className="mt-4">
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); loadUsers(q).catch((x) => setErr(x.message)); }}>
            <input aria-label="Search users" className="input min-w-0 flex-1" placeholder="Search by email or name" value={q} onChange={(e) => setQ(e.target.value)} />
            <button className="btn btn-ghost">Search</button>
          </form>
          <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-card text-sm">
            {users.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                <span><b>{u.email}</b> {u.is_admin && <span className="rounded-full bg-violet px-2 py-0.5 text-xs text-white">admin</span>} {u.is_suspended && <span className="rounded-full bg-coral/20 px-2 py-0.5 text-xs text-coral">suspended</span>}<br /><span className="text-muted">{u.plan_id} · {u.credits} credits</span></span>
                <span className="flex flex-wrap gap-2">
                  <button className="btn btn-ghost !min-h-9 text-xs" onClick={() => { const a = prompt(`Credits to add (use a minus sign to remove) for ${u.email}`); if (!a) return; const reason = prompt("Reason (shown in the audit log)"); if (!reason) return; act(async () => { await api(`/admin/users/${u.id}/credits`, { body: { amount: Number(a), reason } }); await loadUsers(q); }, "Credits updated."); }}>Credits</button>
                  <select aria-label={`Plan for ${u.email}`} className="input !min-h-9 !py-1 text-xs" value={u.plan_id} onChange={(e) => act(async () => { await api(`/admin/users/${u.id}/plan`, { body: { plan_id: e.target.value } }); await loadUsers(q); }, "Plan changed.")}>
                    {["free", "starter", "creator", "business"].map((p) => <option key={p}>{p}</option>)}
                  </select>
                  <button className="btn btn-ghost !min-h-9 text-xs" onClick={() => act(async () => { await api(`/admin/users/${u.id}/suspend`, { body: { suspended: !u.is_suspended } }); await loadUsers(q); }, u.is_suspended ? "Unsuspended." : "Suspended.")}>{u.is_suspended ? "Unsuspend" : "Suspend"}</button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "Plans" && (
        <section aria-label="Plans" className="mt-4 space-y-3">
          <p className="text-sm text-muted">Prices are per month (naira in whole naira, dollars in cents). Changes apply to new purchases and renewals.</p>
          {plans.map((p, i) => (
            <form key={p.id} className="card grid gap-2 p-4 sm:grid-cols-5" onSubmit={(e) => { e.preventDefault(); act(() => api(`/admin/plans/${p.id}`, { method: "PUT", body: p }), `${p.name} saved.`); }}>
              {([["name", "Name"], ["price_ngn_month", "NGN / month"], ["price_usd_month", "USD cents / month"], ["monthly_credits", "Credits"]] as const).map(([k, label]) => (
                <label key={k} className="text-xs font-medium">{label}<input className="input mt-1" value={p[k]} type={k === "name" ? "text" : "number"} min={0} onChange={(e) => setPlans((all) => all.map((x, j) => (j === i ? { ...x, [k]: k === "name" ? e.target.value : Number(e.target.value) } : x)))} /></label>
              ))}
              <button className="btn btn-primary self-end">Save {p.id}</button>
            </form>
          ))}
        </section>
      )}

      {tab === "Excel" && (
        <section aria-label="Excel" className="mt-4">
          <p className="text-sm text-muted">Export plans, users, invoices, the credit ledger and AI usage as one .xlsx. Import changes plan prices and grants credits from the Plans and CreditGrants sheets. Imports are checked first and nothing is applied unless every row is valid.</p>
          <a className="btn btn-primary mt-3" href="/api/admin/export.xlsx">Download export (.xlsx)</a>
          <label className="mt-6 block text-sm font-medium">Import a spreadsheet
            <input type="file" accept=".xlsx" className="input mt-1" onChange={async (e) => { const f = e.target.files?.[0]; if (!f) return; await act(async () => sendXlsx(await f.arrayBuffer(), false)); e.target.value = ""; }} />
          </label>
          {imp && (
            <div className="card mt-3 p-4 text-sm" aria-label="Import check">
              <p><b>{imp.res.ok ? "Ready to apply" : "Fix these problems first"}</b>: {imp.res.summary.plans} plan rows, {imp.res.summary.grants} credit grants ({imp.res.summary.credits_total} credits){imp.res.applied && " · applied"}</p>
              {imp.res.errors.length > 0 && <ul className="mt-2 list-disc pl-5 text-coral">{imp.res.errors.map((x, i) => <li key={i}>{x.sheet}{x.row ? ` row ${x.row}` : ""}: {x.error}</li>)}</ul>}
              {imp.res.ok && !imp.res.applied && <button className="btn btn-primary mt-3" onClick={() => act(() => sendXlsx(imp.bytes, true))}>Apply import</button>}
            </div>
          )}
        </section>
      )}

      {tab === "Integrations" && (
        <section aria-label="Integrations" className="mt-4 space-y-6">
          <form className="card p-4" onSubmit={(e) => { e.preventDefault(); act(async () => { await api("/admin/key", { body: { key } }); setKey(""); }, "OpenRouter key saved."); }}>
            <h2 className="font-semibold">OpenRouter key</h2>
            <p className="text-sm text-muted">The only key this app needs. Stored encrypted.</p>
            <input aria-label="OpenRouter key" type="password" className="input mt-2" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk-or-…" autoComplete="off" required />
            <button className="btn btn-primary mt-2">Save key</button>
          </form>
          <form className="card p-4" onSubmit={(e) => { e.preventDefault(); act(async () => { const x = await api<{ redirect_uri: string }>("/admin/youtube", { body: yt }); setYt({ client_id: "", client_secret: "" }); setMsg(`YouTube saved. In Google Cloud, set the OAuth redirect URI to ${x.redirect_uri}`); }); }}>
            <h2 className="font-semibold">YouTube publishing (optional)</h2>
            <p className="text-sm text-muted">Needs a Google OAuth client you create yourself. Without it, people use the publish pack. Not tested against live Google yet.</p>
            <input aria-label="YouTube client id" className="input mt-2" value={yt.client_id} onChange={(e) => setYt({ ...yt, client_id: e.target.value })} placeholder="Client id" required />
            <input aria-label="YouTube client secret" type="password" className="input mt-2" value={yt.client_secret} onChange={(e) => setYt({ ...yt, client_secret: e.target.value })} placeholder="Client secret" autoComplete="off" required />
            <button className="btn btn-primary mt-2">Save YouTube settings</button>
          </form>
        </section>
      )}

      {tab === "Audit" && (
        <section aria-label="Audit log" className="mt-4">
          {audit.length === 0 ? <p className="text-sm text-muted">Nothing logged yet.</p> : (
            <ul className="divide-y divide-line rounded-2xl border border-line bg-card text-sm">
              {audit.map((a, i) => <li key={i} className="p-3"><b>{a.action}</b> by {a.actor} <span className="text-muted">· {new Date(a.at + "Z").toLocaleString()}</span><br /><span className="break-all text-xs text-muted">{JSON.stringify(a.detail)}</span></li>)}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}
