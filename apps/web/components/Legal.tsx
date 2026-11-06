export function Legal({ title, updated, sections }: { title: string; updated: string; sections: [string, string[]][] }) {
  return (
    <div className="mx-auto max-w-3xl px-5 py-14">
      <h1 className="text-4xl font-bold">{title}</h1>
      <p className="mt-2 text-sm text-muted">Last updated {updated}</p>
      <div className="prose-clue mt-6">
        {sections.map(([h, ps]) => (
          <section key={h}>
            <h2>{h}</h2>
            {ps.map((p) => <p key={p}>{p}</p>)}
          </section>
        ))}
      </div>
    </div>
  );
}
