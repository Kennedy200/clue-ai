"use client";
import { useState } from "react";
import { api, csrfToken } from "@/lib/api";

type Result = { score: number; grade: string; parts: Record<string, number>; max: Record<string, number>; tips: string[]; words: number; est_seconds: number };
type Fix = { source: "ai" | "template"; hooks: string[]; script?: string; before: number; after?: number; changes?: string[] };
const LABEL: Record<string, string> = { hook: "Hook", pacing: "Pacing", clarity: "Clarity", specificity: "Specifics", cta: "Call to action" };

export default function ScorePage() {
  const [script, setScript] = useState("");
  const [res, setRes] = useState<Result | null>(null);
  const [fix, setFix] = useState<Fix | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [card, setCard] = useState("");

  async function run<T>(fn: () => Promise<T>) {
    setErr(""); setBusy(true);
    try { return await fn(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  const doScore = () => run(async () => { setFix(null); setCard(""); setRes(await api<Result>("/score", { body: { script } })); });
  const doFix = () => run(async () => setFix(await api<Fix>("/score/fix-hook", { body: { script } })));
  const doCard = () => run(async () => {
    const r = await fetch("/api/score/card", { method: "POST", headers: { "content-type": "application/json", "x-csrf-token": csrfToken() }, body: JSON.stringify({ script }) });
    if (!r.ok) throw new Error("Could not make the card. Try again.");
    setCard(URL.createObjectURL(await r.blob()));
  });
  const useHook = (h: string) => { const rest = script.replace(/^[^.!?\n]*[.!?]?\s*/, ""); setScript(`${h} ${rest}`.trim()); setFix(null); setRes(null); };

  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold">Clue Score</h1>
      <p className="mt-1 text-muted">Free and instant. It runs on your own device&apos;s server, so it works without an AI key and costs no credits.</p>
      <label htmlFor="sc" className="mt-5 block text-sm font-medium">Your script</label>
      <textarea id="sc" className="input mt-1 min-h-40" maxLength={6000} value={script} onChange={(e) => setScript(e.target.value)} placeholder="Paste the words you will say in the video…" />
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="btn btn-primary" disabled={busy || script.trim().length < 10} onClick={doScore}>Score my script</button>
        <button className="btn btn-ghost" disabled={busy || script.trim().length < 10} onClick={doFix}>Fix my hook</button>
      </div>
      {err && <p role="alert" className="mt-3 text-sm text-coral">{err}</p>}

      {res && (
        <section aria-label="Score result" className="card mt-6 p-5">
          <div className="flex items-center gap-4">
            <div className="relative grid h-24 w-24 place-items-center rounded-full bg-ink text-white">
              <svg viewBox="0 0 100 100" className="absolute inset-0 -rotate-90" aria-hidden><circle cx="50" cy="50" r="45" fill="none" stroke="#2a2250" strokeWidth="8" /><circle key={res.score} className="ring" cx="50" cy="50" r="45" fill="none" stroke={res.score >= 70 ? "#c8ff3d" : res.score >= 45 ? "#ffbe50" : "#ff5c7a"} strokeWidth="8" strokeLinecap="round" strokeDasharray="283" strokeDashoffset={283 - (283 * res.score) / 100} /></svg>
              <span key={`n${res.score}`} className="count-up relative font-display text-4xl font-bold" style={{ ["--to" as string]: res.score }} aria-hidden />
              <span className="sr-only" data-testid="score">{res.score}</span>
            </div>
            <div><p className="text-xl font-bold">Grade {res.grade}</p><p className="text-sm text-muted">{res.words} words · about {res.est_seconds} seconds</p></div>
          </div>
          <ul className="mt-4 space-y-2">
            {Object.entries(res.parts).map(([k, v]) => (
              <li key={k} className="text-sm"><div className="flex justify-between"><span>{LABEL[k] ?? k}</span><span>{v}/{res.max[k]}</span></div>
                <div className="mt-1 h-2 rounded-full bg-line"><div className="h-2 rounded-full bg-violet" style={{ width: `${(v / res.max[k]) * 100}%` }} /></div></li>
            ))}
          </ul>
          {res.tips.length > 0 && <><h2 className="mt-5 font-semibold">How to improve it</h2><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{res.tips.map((t) => <li key={t}>{t}</li>)}</ul></>}
          <button className="btn btn-ghost mt-4" disabled={busy} onClick={doCard}>Make my Clue Card</button>
          {card && <div className="mt-4"><img src={card} alt={`Clue Card showing a score of ${res.score}`} className="w-60 rounded-xl" /><a className="btn btn-primary mt-3" href={card} download="clue-card.png">Download card</a></div>}
        </section>
      )}

      {fix && (
        <section aria-label="Hook options" className="card mt-6 p-5">
          <h2 className="font-semibold">{fix.source === "ai" ? "Better hooks (AI)" : "Hook ideas"}</h2>
          {fix.source === "template" && <p className="mt-1 text-xs text-muted">AI is not set up, so these are simple templates. Add a free OpenRouter key in Setup for tailored rewrites.</p>}
          {fix.after != null && <p className="mt-1 text-sm">Score {fix.before} → {fix.after}</p>}
          <ul className="mt-3 space-y-2">
            {fix.hooks.map((h) => <li key={h} className="flex items-start justify-between gap-3 rounded-xl bg-line p-3 text-sm"><span>{h}</span><button className="btn btn-ghost !min-h-8 shrink-0 text-xs" onClick={() => useHook(h)}>Use this</button></li>)}
          </ul>
        </section>
      )}
    </div>
  );
}
