import Link from "next/link";
import { Logo } from "@/components/Logo";

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <header className="flex items-center justify-between">
        <Logo />
        <nav className="flex gap-2">
          <Link href="/login" className="btn btn-ghost">Sign in</Link>
          <Link href="/signup" className="btn btn-primary">Get started</Link>
        </nav>
      </header>
      <section className="py-20">
        <h1 className="text-4xl font-bold sm:text-6xl">
          Scripts in. <span className="rounded-lg bg-lime px-2 text-ink">Shorts</span> out.
        </h1>
        <p className="mt-5 max-w-xl text-lg text-muted">
          Turn an idea, a script or a long video into a captioned vertical short with an AI voiceover. Built to run on a
          laptop and on a cheap phone.
        </p>
        <Link href="/signup" className="btn btn-primary mt-8">Create your first video</Link>
      </section>
    </main>
  );
}
