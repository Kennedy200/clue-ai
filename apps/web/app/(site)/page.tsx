import Link from "next/link";
import { Faq, JsonLd, faqLd } from "@/components/Site";
import { HeroDemo } from "@/components/HeroDemo";
import { FAQ } from "@/lib/faq";
import { features } from "@/lib/content";
import { getReviews } from "@/lib/server-api";

const STYLES = [
  ["Text Story", "Narrated storytime over a looping background with animated captions."],
  ["Video Story", "A different visual for every scene of your script."],
  ["Video Commentary", "Your clip, with AI commentary and the original audio ducked."],
  ["Split Screen", "Main content on top, a satisfying loop underneath."],
  ["Video Ranking", "Top-N countdowns with number badges and one-line voiceovers."],
  ["Auto Clipping", "Long video in, best short clips out, reframed to vertical."],
];

export default async function Home() {
  const reviews = await getReviews();
  const tools = features().filter((f) => f.kind !== "comparison").slice(0, 8);
  return (
    <>
      <JsonLd data={faqLd(FAQ)} />
      <JsonLd data={{ "@context": "https://schema.org", "@type": "Organization", name: "Clue AI", url: process.env.SITE_URL || "http://localhost:3000" }} />
      <section className="mx-auto grid max-w-6xl items-center gap-10 px-5 py-14 md:grid-cols-2 md:py-24">
        <div>
          <p className="font-mono text-sm text-violet">Open source · runs on your laptop</p>
          <h1 className="mt-3 text-4xl font-bold leading-tight sm:text-6xl">
            Scripts in. <span className="rounded-lg bg-lime px-2 text-ink">Shorts</span> out.
          </h1>
          <p className="mt-5 max-w-xl text-lg text-muted">
            Turn an idea, a script or a long video into a captioned vertical short with an AI voiceover. No camera and no editing skills needed.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/signup" className="btn btn-primary">Create your first video</Link>
            <Link href="/features" className="btn btn-ghost">See what it can do</Link>
          </div>
        </div>
        <HeroDemo />
      </section>

      <section className="mx-auto max-w-6xl px-5 py-12" aria-labelledby="how">
        <h2 id="how" className="text-3xl font-bold">Three steps, no learning curve</h2>
        <ol className="mt-8 grid gap-4 md:grid-cols-3">
          {[["1. Input", "Upload footage, paste a script, or type an idea."], ["2. Generate", "The AI writes scenes, voices them and builds word-synced captions."], ["3. Edit and export", "Tweak anything on the timeline, then render a 1080×1920 MP4."]].map(([t, d]) => (
            <li key={t} className="card p-5"><h3 className="text-xl font-semibold">{t}</h3><p className="mt-2 text-muted">{d}</p></li>
          ))}
        </ol>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-12" aria-labelledby="styles">
        <h2 id="styles" className="text-3xl font-bold">Six ways to make a video</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {STYLES.map(([t, d]) => (<div key={t} className="card p-5"><h3 className="text-lg font-semibold">{t}</h3><p className="mt-2 text-sm text-muted">{d}</p></div>))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-12" aria-labelledby="tools">
        <h2 id="tools" className="text-3xl font-bold">Tools you can use on their own</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {tools.map((f) => (
            <Link key={f.slug} href={`/features/${f.slug}`} className="card p-4 transition-transform hover:-translate-y-0.5">
              <h3 className="font-semibold">{f.title}</h3><p className="mt-1 text-sm text-muted">{f.description}</p>
            </Link>
          ))}
        </div>
        <Link href="/features" className="mt-6 inline-block font-semibold underline">All features</Link>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-12" aria-labelledby="score">
        <div className="card grid items-center gap-6 bg-ink p-8 text-paper md:grid-cols-2" style={{ background: "var(--ink)" }}>
          <div>
            <h2 id="score" className="text-3xl font-bold">Know your hook before you post</h2>
            <p className="mt-3 text-paper/80">Every video gets a Clue Score from 0 to 100 based on hook, pacing, clarity and payoff, with a one-tap rewrite of the first three seconds.</p>
          </div>
          <p className="font-mono text-7xl font-bold text-lime md:text-right" aria-hidden>87</p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-12" aria-labelledby="community">
        <h2 id="community" className="text-3xl font-bold">From creators</h2>
        {reviews.length === 0 ? (
          <p className="mt-4 text-muted">No reviews yet. Be one of the first creators to share how Clue AI works for you.</p>
        ) : (
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {reviews.map((r, i) => (<figure key={i} className="card p-5"><blockquote>{r.body}</blockquote><figcaption className="mt-2 text-sm text-muted">{r.name} · {r.rating}/5</figcaption></figure>))}
          </div>
        )}
      </section>

      <section className="mx-auto max-w-3xl px-5 py-12" aria-labelledby="faq">
        <h2 id="faq" className="mb-6 text-3xl font-bold">Questions</h2>
        <Faq items={FAQ} />
      </section>

      <section className="mx-auto max-w-6xl px-5 py-12 text-center">
        <h2 className="text-3xl font-bold">Make your first short today</h2>
        <Link href="/signup" className="btn btn-primary mt-6">Get started free</Link>
      </section>
    </>
  );
}
