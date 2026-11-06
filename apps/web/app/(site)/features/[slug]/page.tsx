import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Faq, JsonLd, faqLd } from "@/components/Site";
import { SITE, feature, features } from "@/lib/content";

type P = { params: Promise<{ slug: string }> };

export const dynamicParams = false;
export const generateStaticParams = () => features().map((f) => ({ slug: f.slug }));

export async function generateMetadata({ params }: P): Promise<Metadata> {
  const f = feature((await params).slug);
  if (!f) return {};
  return { title: f.title, description: f.description, alternates: { canonical: `/features/${f.slug}` }, openGraph: { title: f.h1, description: f.description } };
}

export default async function FeaturePage({ params }: P) {
  const f = feature((await params).slug);
  if (!f) notFound();
  const related = f.related.map((s) => feature(s)).filter((x) => !!x);
  return (
    <article className="mx-auto max-w-4xl px-5 py-14">
      <JsonLd data={faqLd(f.faq)} />
      <JsonLd data={{ "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [
        { "@type": "ListItem", position: 1, name: "Features", item: `${SITE}/features` },
        { "@type": "ListItem", position: 2, name: f.title, item: `${SITE}/features/${f.slug}` }] }} />
      <p className="text-sm text-muted"><Link href="/features" className="underline">Features</Link> / {f.title}</p>
      <h1 className="mt-3 text-4xl font-bold sm:text-5xl">{f.h1}</h1>
      <p className="mt-5 max-w-2xl text-lg text-muted">{f.intro}</p>
      <Link href="/signup" className="btn btn-primary mt-6">Try it free</Link>

      <h2 className="mt-14 text-2xl font-bold">Why it helps</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {f.benefits.map((b) => (<div key={b.title} className="card p-5"><h3 className="font-semibold">{b.title}</h3><p className="mt-2 text-sm text-muted">{b.text}</p></div>))}
      </div>

      <h2 className="mt-14 text-2xl font-bold">How it works</h2>
      <ol className="mt-4 space-y-3">
        {f.steps.map((s, i) => (<li key={s} className="card flex gap-3 p-4"><span className="font-mono font-bold text-violet">{i + 1}</span><span>{s}</span></li>))}
      </ol>

      <h2 className="mt-14 text-2xl font-bold">Questions</h2>
      <div className="mt-4"><Faq items={f.faq} /></div>

      {related.length > 0 && (<>
        <h2 className="mt-14 text-2xl font-bold">Related</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          {related.map((r) => r && <Link key={r.slug} href={`/features/${r.slug}`} className="btn btn-ghost">{r.title}</Link>)}
        </div>
      </>)}
    </article>
  );
}
