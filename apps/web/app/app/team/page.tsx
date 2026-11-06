"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type TeamLite = { id: string; name: string; role: string };
type Detail = { id: string; name: string; role: string; members: { user_id: string; email: string; name: string; role: string }[]; invites: { id: string; email: string; role: string }[] };
type Vid = { project_id: string; title: string; style: string; by: string; url: string | null };
type Proj = { id: string; title: string; status: string };
const RANK: Record<string, number> = { viewer: 1, editor: 2, admin: 3, owner: 4 };

export default function TeamPage() {
  const [teams, setTeams] = useState<TeamLite[]>([]);
  const [cur, setCur] = useState<string>("");
  const [d, setD] = useState<Detail | null>(null);
  const [vids, setVids] = useState<Vid[]>([]);
  const [mine, setMine] = useState<Proj[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [share, setShare] = useState("");

  const loadTeams = useCallback(async () => {
    const t = await api<TeamLite[]>("/teams");
    setTeams(t);
    setCur((c) => c || t[0]?.id || "");
  }, []);
  const loadTeam = useCallback(async (id: string) => {
    if (!id) return setD(null);
    const [x, v] = await Promise.all([api<Detail>(`/teams/${id}`), api<Vid[]>(`/teams/${id}/videos`)]);
    setD(x); setVids(v);
  }, []);
  async function act(fn: () => Promise<unknown>, ok = "") {
    setErr(""); setMsg("");
    try { await fn(); if (ok) setMsg(ok); await loadTeams(); await loadTeam(cur); } catch (e) { setErr((e as Error).message); }
  }

  useEffect(() => {
    loadTeams().catch((e) => setErr(e.message));
    api<Proj[]>("/projects").then(setMine).catch(() => {});
    const tok = new URLSearchParams(window.location.search).get("invite");
    if (tok) api("/teams/accept", { body: { token: tok } }).then(() => { setMsg("You joined the team."); history.replaceState(null, "", "/app/team"); return loadTeams(); }).catch((e) => setErr(e.message));
  }, [loadTeams]);
  useEffect(() => { loadTeam(cur).catch((e) => setErr(e.message)); }, [cur, loadTeam]);

  const rank = d ? RANK[d.role] : 0;
  return (
    <div className="max-w-3xl">
      <h1 className="text-3xl font-bold">Team</h1>
      <p className="mt-1 text-sm text-muted">Share finished videos and brand kits with people you work with. Roles: viewer sees, editor shares and edits kits, admin manages people, owner runs the team.</p>
      <div aria-live="polite">
        {msg && <p role="status" className="mt-3 rounded-xl bg-lime/40 p-3 text-sm">{msg}</p>}
        {err && <p role="alert" className="mt-3 rounded-xl bg-coral/10 p-3 text-sm text-coral">{err}</p>}
      </div>

      <form className="card mt-5 flex gap-2 p-4" onSubmit={(e) => { e.preventDefault(); act(async () => { const t = await api<TeamLite>("/teams", { body: { name } }); setName(""); setCur(t.id); }, "Team created."); }}>
        <input aria-label="New team name" className="input min-w-0 flex-1" placeholder="New team name" value={name} onChange={(e) => setName(e.target.value)} minLength={2} required />
        <button className="btn btn-primary">Create team</button>
      </form>

      {teams.length > 0 && (
        <div role="tablist" aria-label="Your teams" className="mt-5 flex flex-wrap gap-2">
          {teams.map((t) => <button key={t.id} role="tab" aria-selected={cur === t.id} className={`rounded-xl px-3 py-2 text-sm font-medium ${cur === t.id ? "bg-violet text-white" : "bg-line"}`} onClick={() => setCur(t.id)}>{t.name} <span className="opacity-70">· {t.role}</span></button>)}
        </div>
      )}

      {d && (
        <>
          <h2 className="mt-6 text-xl font-semibold">People</h2>
          <ul className="mt-2 divide-y divide-line rounded-2xl border border-line bg-card text-sm">
            {d.members.map((m) => (
              <li key={m.user_id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                <span><b>{m.name || m.email}</b> <span className="text-muted">{m.email}</span></span>
                <span className="flex items-center gap-2">
                  {rank >= 3 && m.role !== "owner" ? (
                    <select aria-label={`Role for ${m.email}`} className="input !min-h-9 !py-1" value={m.role} onChange={(e) => act(() => api(`/teams/${d.id}/members/${m.user_id}`, { method: "PUT", body: { role: e.target.value } }), "Role updated.")}>
                      <option value="viewer">viewer</option><option value="editor">editor</option>{d.role === "owner" && <option value="admin">admin</option>}
                    </select>
                  ) : <span className="rounded-full bg-line px-2 py-0.5 text-xs">{m.role}</span>}
                  {m.role !== "owner" && rank >= 3 && <button className="btn btn-ghost !min-h-9 text-xs" onClick={() => confirm(`Remove ${m.email}?`) && act(() => api(`/teams/${d.id}/members/${m.user_id}`, { method: "DELETE" }), "Removed.")}>Remove</button>}
                </span>
              </li>
            ))}
            {d.invites.map((i) => <li key={i.id} className="p-3 text-muted">Invited: {i.email} as {i.role} (pending)</li>)}
          </ul>
          {rank >= 3 && (
            <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); act(async () => { await api(`/teams/${d.id}/invite`, { body: { email, role } }); setEmail(""); }, "Invite sent. In development it appears in the dev inbox."); }}>
              <input aria-label="Invite by email" type="email" className="input min-w-0 flex-1" placeholder="friend@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
              <select aria-label="Invite role" className="input" value={role} onChange={(e) => setRole(e.target.value)}><option>viewer</option><option>editor</option>{d.role === "owner" && <option>admin</option>}</select>
              <button className="btn btn-primary">Invite</button>
            </form>
          )}

          <h2 className="mt-8 text-xl font-semibold">Team videos</h2>
          {rank >= 2 && (
            <div className="mt-2 flex gap-2">
              <select aria-label="Video to share" className="input min-w-0 flex-1" value={share} onChange={(e) => setShare(e.target.value)}>
                <option value="">Pick one of your finished videos…</option>
                {mine.filter((p) => p.status === "done").map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
              <button className="btn btn-ghost" disabled={!share} onClick={() => act(() => api(`/teams/${d.id}/share`, { body: { project_id: share } }), "Shared with the team.")}>Share</button>
            </div>
          )}
          {vids.length === 0 ? <p className="mt-2 text-sm text-muted">Nothing shared yet.</p> : (
            <ul className="mt-3 grid gap-3 sm:grid-cols-2">
              {vids.map((v) => (
                <li key={v.project_id} className="card p-3 text-sm">
                  <b>{v.title}</b><p className="text-muted">by {v.by}</p>
                  {v.url && <video src={v.url} controls preload="none" className="mt-2 aspect-[9/16] w-full max-w-[200px] rounded-xl bg-ink" />}
                  {rank >= 2 && <button className="btn btn-ghost mt-2 !min-h-9 text-xs" onClick={() => act(() => api(`/teams/${d.id}/share/${v.project_id}`, { method: "DELETE" }), "Removed from the team.")}>Stop sharing</button>}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-8">
            {d.role === "owner" ? <button className="btn btn-ghost text-coral" onClick={() => confirm("Delete this team? Shared videos stay in their owners' accounts.") && act(async () => { await api(`/teams/${d.id}`, { method: "DELETE" }); setCur(""); setD(null); }, "Team deleted.")}>Delete team</button>
              : <button className="btn btn-ghost" onClick={() => confirm("Leave this team?") && act(async () => { const me = await api<{ id: string }>("/auth/me"); await api(`/teams/${d.id}/members/${me.id}`, { method: "DELETE" }); setCur(""); setD(null); }, "You left the team.")}>Leave team</button>}
          </div>
        </>
      )}
    </div>
  );
}
