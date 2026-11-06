"use client";
import Link from "next/link";
import { use } from "react";
import { PANELS, TOOLS } from "@/components/ToolPanels";

export default function Tool({ params }: { params: Promise<{ tool: string }> }) {
  const { tool } = use(params);
  const meta = TOOLS[tool];
  const Panel = PANELS[tool];
  if (!meta || !Panel) return <p>That tool does not exist. <Link className="underline" href="/app/tools">Back to tools</Link></p>;
  return (
    <div>
      <p className="text-sm text-muted"><Link href="/app/tools" className="underline">Tools</Link> / {meta.title}</p>
      <h1 className="mt-1 text-3xl font-bold">{meta.title}</h1>
      <p className="mb-6 mt-1 text-muted">{meta.blurb} <span className="font-medium">Cost: {meta.cost}.</span></p>
      <Panel />
    </div>
  );
}
