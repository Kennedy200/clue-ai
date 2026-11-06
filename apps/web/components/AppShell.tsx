"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Me, getMe, logout } from "@/lib/api";
import { Logo } from "./Logo";

type Ctx = { me: Me; refresh: () => Promise<void> };
const MeCtx = createContext<Ctx | null>(null);
export const useMe = () => {
  const c = useContext(MeCtx);
  if (!c) throw new Error("useMe outside AppShell");
  return c;
};

const NAV = [["/app", "Home", "⌂"], ["/app/create/text_story", "Create", "＋"], ["/app/tools", "Tools", "✦"], ["/app/media", "Media", "▣"], ["/app/projects", "Videos", "▶"]] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const r = useRouter();
  const path = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const refresh = useCallback(async () => {
    const m = await getMe();
    if (!m) { r.replace("/login"); return; }
    setMe(m);
  }, [r]);
  useEffect(() => { refresh().catch(() => r.replace("/login")); }, [refresh, r]);
  if (!me) return <main className="p-10 text-muted" aria-busy="true">Loading…</main>;
  const inEditor = path.startsWith("/app/editor");
  const unlimited = me.mode === "self_host";
  const active = (h: string) => (h === "/app" ? path === "/app" : path.startsWith(h.split("/").slice(0, 3).join("/")));
  return (
    <MeCtx.Provider value={{ me, refresh }}>
      <header className="sticky top-0 z-30 border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link href="/app" aria-label="Clue AI home"><Logo size={28} /></Link>
          <nav aria-label="Main" className="hidden items-center gap-1 sm:flex">
            {NAV.map(([h, t]) => (
              <Link key={h} href={h} className={`rounded-xl px-3 py-2 text-sm font-medium ${active(h) ? "bg-violet text-white" : "hover:bg-line"}`}>{t}</Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-lime px-3 py-1 font-mono text-xs font-bold text-ink" title="Your credits">{unlimited ? "∞ credits" : `${me.credits} credits`}</span>
            <button className="btn btn-ghost !min-h-9 !px-3 text-sm" onClick={async () => { await logout(); r.push("/"); }}>Sign out</button>
          </div>
        </div>
      </header>
      <div className={`mx-auto max-w-5xl px-4 pt-6 ${inEditor ? "pb-6" : "pb-28 sm:pb-10"}`}>{children}</div>
      {!inEditor && <nav aria-label="Main mobile" className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-card sm:hidden">
        {NAV.map(([h, t, ico]) => (
          <Link key={h} href={h} className={`flex min-h-14 flex-col items-center justify-center text-xs ${active(h) ? "font-bold text-violet" : "text-muted"}`}>
            <span aria-hidden className="text-lg leading-none">{ico}</span>{t}
          </Link>
        ))}
      </nav>}
    </MeCtx.Provider>
  );
}
