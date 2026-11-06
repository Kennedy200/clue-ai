/** Server-only content loaders for features.json and content/blog/*.md. */
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.cwd(), "..", "..", "content");
export const SITE = process.env.NEXT_PUBLIC_SITE_URL || process.env.SITE_URL || "http://localhost:3000";

export type Feature = {
  slug: string; title: string; h1: string; description: string; intro: string; kind?: "comparison";
  benefits: { title: string; text: string }[]; steps: string[]; faq: { q: string; a: string }[]; related: string[];
};

export function features(): Feature[] {
  return JSON.parse(fs.readFileSync(path.join(ROOT, "features.json"), "utf8"));
}
export const feature = (slug: string) => features().find((f) => f.slug === slug);

export type Post = { slug: string; title: string; date: string; description: string; tags: string[]; body: string };

function parsePost(file: string): Post {
  const raw = fs.readFileSync(path.join(ROOT, "blog", file), "utf8").replace(/\r\n/g, "\n");
  const m = raw.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) throw new Error(`Bad frontmatter in ${file}`);
  const meta: Record<string, string> = {};
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^(\w+):\s*(.*)$/);
    if (kv) meta[kv[1]] = kv[2];
  }
  const tags = JSON.parse(meta.tags || "[]") as string[];
  const str = (v: string) => v.replace(/^"|"$/g, "");
  return { slug: file.replace(/\.md$/, ""), title: str(meta.title), date: str(meta.date), description: str(meta.description), tags, body: m[2].trim() };
}

export function posts(): Post[] {
  return fs.readdirSync(path.join(ROOT, "blog")).filter((f) => f.endsWith(".md")).map(parsePost).sort((a, b) => b.date.localeCompare(a.date));
}
export const post = (slug: string) => posts().find((p) => p.slug === slug);
