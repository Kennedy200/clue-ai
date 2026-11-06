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
        <Link href="/app/brand" className="card p-4 transition-transform hover:-translate-y-0.5">
          <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">Brand kits</h2><span className="shrink-0 rounded-full bg-line px-2 py-0.5 text-xs">Creator+</span></div>
          <p className="mt-1 text-sm text-muted">Save your caption look and apply it in one tap.</p>
        </Link>
        <Link href="/app/bulk" className="card p-4 transition-transform hover:-translate-y-0.5">
          <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">Bulk create</h2><span className="shrink-0 rounded-full bg-line px-2 py-0.5 text-xs">Business</span></div>
          <p className="mt-1 text-sm text-muted">Make up to 25 videos from a CSV spreadsheet.</p>
        </Link>
        <Link href="/app/calendar" className="card p-4 transition-transform hover:-translate-y-0.5">
          <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">Content calendar</h2><span className="shrink-0 rounded-full bg-line px-2 py-0.5 text-xs">Free</span></div>
          <p className="mt-1 text-sm text-muted">Plan posts, get a publish pack, upload to YouTube.</p>
        </Link>
        <Link href="/app/team" className="card p-4 transition-transform hover:-translate-y-0.5">
          <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">Team</h2><span className="shrink-0 rounded-full bg-line px-2 py-0.5 text-xs">Business</span></div>
          <p className="mt-1 text-sm text-muted">Share videos and brand kits with your people.</p>
        </Link>
        <Link href="/app/analytics" className="card p-4 transition-transform hover:-translate-y-0.5">
          <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">Your numbers</h2><span className="shrink-0 rounded-full bg-line px-2 py-0.5 text-xs">Free</span></div>
          <p className="mt-1 text-sm text-muted">Videos made and credits spent.</p>
        </Link>
        <Link href="/app/billing" className="card p-4 transition-transform hover:-translate-y-0.5">
          <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">Billing and credits</h2><span className="shrink-0 rounded-full bg-line px-2 py-0.5 text-xs"></span></div>
          <p className="mt-1 text-sm text-muted">Plans, top-ups, invoices and invites.</p>
        </Link>
        <Link href="/app/score" className="card p-4 transition-transform hover:-translate-y-0.5">
          <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">Clue Score</h2><span className="shrink-0 rounded-full bg-lime px-2 py-0.5 text-xs">Free</span></div>
          <p className="mt-1 text-sm text-muted">Score your script out of 100, see exactly what to fix, fix your hook, and share a Clue Card.</p>
        </Link>
      </div>
    </div>
  );
}
