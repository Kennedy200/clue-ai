import type { Metadata } from "next";
import Link from "next/link";
import { features } from "@/lib/content";

export const metadata: Metadata = {
  title: "Features",
  description: "Every Clue AI tool: voiceover, captions, clip maker, script and idea generators, thumbnails and editors for Shorts, TikTok and Reels.",
  alternates: { canonical: "/features" },
};

export default function Features() {
  const all = features();
  const tools = all.filter((f) => f.kind !== "comparison");
  const compare = all.filter((f) => f.kind === "comparison");
  return (
    <div className="mx-auto max-w-6xl px-5 py-14">
      <h1 className="text-4xl font-bold sm:text-5xl">Everything you need to make shorts</h1>
      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tools.map((f) => (
          <Link key={f.slug} href={`/features/${f.slug}`} className="card p-5 transition-transform hover:-translate-y-0.5">
            <h2 className="text-lg font-semibold">{f.title}</h2><p className="mt-2 text-sm text-muted">{f.description}</p>
          </Link>
        ))}
      </div>
      <h2 className="mt-14 text-2xl font-bold">Comparisons</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        {compare.map((f) => (
          <Link key={f.slug} href={`/features/${f.slug}`} className="card p-5"><h3 className="font-semibold">{f.title}</h3><p className="mt-2 text-sm text-muted">{f.description}</p></Link>
        ))}
      </div>
    </div>
  );
}
