import type { MetadataRoute } from "next";
import { SITE, features, posts } from "@/lib/content";

export default function sitemap(): MetadataRoute.Sitemap {
  const fixed = ["", "/pricing", "/features", "/blog", "/about", "/contact", "/privacy", "/terms", "/refund"];
  return [
    ...fixed.map((p) => ({ url: `${SITE}${p}` })),
    ...features().map((f) => ({ url: `${SITE}/features/${f.slug}` })),
    ...posts().map((p) => ({ url: `${SITE}/blog/${p.slug}`, lastModified: p.date })),
  ];
}
