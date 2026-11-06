import Link from "next/link";
import { Logo } from "./Logo";

export function SiteHeader() {
  return (
    <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
      <Link href="/" aria-label="Clue AI home"><Logo /></Link>
      <nav aria-label="Main" className="hidden items-center gap-6 text-sm font-medium md:flex">
        <Link href="/features">Features</Link>
        <Link href="/pricing">Pricing</Link>
        <Link href="/blog">Blog</Link>
        <Link href="/about">About</Link>
      </nav>
      <div className="flex gap-2">
        <Link href="/login" className="btn btn-ghost hidden sm:inline-flex">Sign in</Link>
        <Link href="/signup" className="btn btn-primary">Get started</Link>
      </div>
    </header>
  );
}

const cols: { h: string; links: [string, string][] }[] = [
  { h: "Product", links: [["Features", "/features"], ["Pricing", "/pricing"], ["Blog", "/blog"]] },
  { h: "Company", links: [["About", "/about"], ["Contact", "/contact"]] },
  { h: "Legal", links: [["Privacy", "/privacy"], ["Terms", "/terms"], ["Refunds", "/refund"]] },
];

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 sm:grid-cols-4">
        <div>
          <Logo size={28} />
          <p className="mt-3 max-w-xs text-sm text-muted">Open-source short video maker. Not affiliated with any other product.</p>
        </div>
        {cols.map((c) => (
          <nav key={c.h} aria-label={c.h}>
            <h2 className="text-sm font-semibold">{c.h}</h2>
            <ul className="mt-3 space-y-2 text-sm text-muted">
              {c.links.map(([t, h]) => <li key={h}><Link href={h}>{t}</Link></li>)}
            </ul>
          </nav>
        ))}
      </div>
    </footer>
  );
}

export function JsonLd({ data }: { data: object }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }} />;
}

export function Faq({ items }: { items: { q: string; a: string }[] }) {
  return (
    <div className="divide-y divide-line rounded-2xl border border-line bg-card">
      {items.map((f) => (
        <details key={f.q} className="group p-4">
          <summary className="cursor-pointer list-none font-semibold marker:hidden">{f.q}</summary>
          <p className="mt-2 text-muted">{f.a}</p>
        </details>
      ))}
    </div>
  );
}

export const faqLd = (items: { q: string; a: string }[]) => ({
  "@context": "https://schema.org", "@type": "FAQPage",
  mainEntity: items.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
});
