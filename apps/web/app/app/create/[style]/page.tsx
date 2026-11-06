"use client";
import Link from "next/link";
import { use } from "react";
import { CreateForm, STYLE_INFO } from "@/components/CreateForm";

export default function Create({ params }: { params: Promise<{ style: string }> }) {
  const { style } = use(params);
  return (
    <div>
      <nav aria-label="Video styles" className="-mx-4 mb-6 flex gap-2 overflow-x-auto px-4 pb-1">
        {Object.entries(STYLE_INFO).map(([k, v]) => (
          <Link key={k} href={`/app/create/${k}`} className={`btn shrink-0 !min-h-10 text-sm ${k === style ? "btn-primary" : "btn-ghost"}`}>{v.title}</Link>
        ))}
        <Link href="/app/tools/clips" className="btn btn-ghost shrink-0 !min-h-10 text-sm">Auto Clipping →</Link>
      </nav>
      <CreateForm key={style} style={style} />
    </div>
  );
}
