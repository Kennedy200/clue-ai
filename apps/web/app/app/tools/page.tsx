"use client";
import Link from "next/link";
import { TOOLS } from "@/components/ToolPanels";

export default function ToolsHub() {
  return (
    <div>
      <h1 className="text-3xl font-bold">Tools</h1>
      <p className="mt-1 text-muted">Each one works on its own. The cost is shown before you spend anything.</p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {Object.entries(TOOLS).map(([k, t]) => (
          <Link key={k} href={`/app/tools/${k}`} className="card p-4 transition-transform hover:-translate-y-0.5">
            <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">{t.title}</h2><span className="shrink-0 rounded-full bg-line px-2 py-0.5 text-xs">{t.cost}</span></div>
            <p className="mt-1 text-sm text-muted">{t.blurb}</p>
          </Link>
        ))}
        <Link href="/app/score" className="card p-4 transition-transform hover:-translate-y-0.5">
          <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">Clue Score</h2><span className="shrink-0 rounded-full bg-lime px-2 py-0.5 text-xs">Free</span></div>
          <p className="mt-1 text-sm text-muted">Score your script out of 100, see exactly what to fix, fix your hook, and share a Clue Card.</p>
        </Link>
      </div>
    </div>
  );
}
