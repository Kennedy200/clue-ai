import type { Metadata } from "next";
import Link from "next/link";
import { posts } from "@/lib/content";

export const metadata: Metadata = { title: "Blog", description: "Practical guides on short-form hooks, storytime videos, faceless channels, captions, repurposing and monetisation.", alternates: { canonical: "/blog" } };

export default function Blog() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-14">
      <h1 className="text-4xl font-bold sm:text-5xl">Blog</h1>
      <p className="mt-3 text-muted">Guides for making better short videos. <a className="underline" href="/blog/rss.xml">RSS</a></p>
      <div className="mt-10 space-y-4">
        {posts().map((p) => (
          <Link key={p.slug} href={`/blog/${p.slug}`} className="card block p-5 transition-transform hover:-translate-y-0.5">
            <p className="font-mono text-xs text-muted">{p.date} · {p.tags.join(", ")}</p>
            <h2 className="mt-1 text-xl font-semibold">{p.title}</h2>
            <p className="mt-2 text-sm text-muted">{p.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
