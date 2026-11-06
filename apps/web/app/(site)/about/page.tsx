import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "About", description: "Why Clue AI exists: an open-source short video maker built for creators with limited budgets and bandwidth.", alternates: { canonical: "/about" } };

export default function About() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-14">
      <h1 className="text-4xl font-bold">About Clue AI</h1>
      <div className="prose-clue mt-6">
        <p>Clue AI started in Lagos, with a simple frustration: most AI video tools are priced in dollars, need fast internet, and lock your work behind a subscription. Many talented creators in Nigeria and across Africa work on modest phones, patchy data and tight budgets.</p>
        <p>So Clue AI is built the other way round. It is open source under the MIT licence. It runs on your own computer with local voices and local transcription, uses free AI models when it needs a language model, and keeps its web pages light enough to load on a slow connection.</p>
        <h2>What we believe</h2>
        <ul>
          <li>You should own your videos and your data.</li>
          <li>Tools should be honest about what they can and cannot do.</li>
          <li>Good software should work on the hardware people actually have.</li>
        </ul>
        <h2>Honest limits</h2>
        <p>Clue AI is early. Free AI models have small daily limits, so the app is careful with every request. It does not generate footage with frontier video models, and it does not clone voices. Where something is not ready, the app says so.</p>
        <p>Want to help? Read the <Link href="/contact" className="underline">contact page</Link> or contribute plugins, voices, caption styles and templates on GitHub.</p>
      </div>
    </div>
  );
}
