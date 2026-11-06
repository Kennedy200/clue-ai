import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Markdown } from "@/components/Markdown";
import { JsonLd } from "@/components/Site";
import { SITE, post, posts } from "@/lib/content";

type P = { params: Promise<{ slug: string }> };

export const dynamicParams = false;
export const generateStaticParams = () => posts().map((p) => ({ slug: p.slug }));

export async function generateMetadata({ params }: P): Promise<Metadata> {
  const p = post((await params).slug);
  if (!p) return {};
  return { title: p.title, description: p.description, alternates: { canonical: `/blog/${p.slug}` }, openGraph: { type: "article", title: p.title, description: p.description, publishedTime: p.date } };
}

export default async function BlogPost({ params }: P) {
  const p = post((await params).slug);
  if (!p) notFound();
  return (
    <article className="mx-auto max-w-3xl px-5 py-14">
      <JsonLd data={{ "@context": "https://schema.org", "@type": "Article", headline: p.title, datePublished: p.date, description: p.description, mainEntityOfPage: `${SITE}/blog/${p.slug}` }} />
      <p className="text-sm text-muted"><Link href="/blog" className="underline">Blog</Link> · {p.date}</p>
      <h1 className="mt-2 text-4xl font-bold">{p.title}</h1>
      <div className="mt-8"><Markdown source={p.body} /></div>
      <div className="card mt-12 p-5">
        <h2 className="font-semibold">Ready to make one?</h2>
        <Link href="/signup" className="btn btn-primary mt-3">Try Clue AI free</Link>
      </div>
    </article>
  );
}
