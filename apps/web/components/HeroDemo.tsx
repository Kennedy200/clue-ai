const SCORES = [92, 87, 81];

/** CSS-only demo (no JavaScript, no video file): a wide video is scanned, then three vertical clips appear with counting scores. */
export function HeroDemo() {
  return (
    <div className="card relative mx-auto w-full max-w-md overflow-hidden p-4" role="img" aria-label="Animation: a long video is scanned and three scored vertical clips appear">
      <div className="relative h-28 overflow-hidden rounded-xl bg-ink">
        <div className="scan-line absolute inset-y-0 w-1 bg-lime" />
        <div className="absolute left-3 top-3 font-mono text-xs text-paper/80">podcast-episode.mp4 · 42:10</div>
        <svg className="absolute bottom-0 h-10 w-full" viewBox="0 0 200 20" preserveAspectRatio="none" aria-hidden>
          <polyline fill="none" stroke="#a592ff" strokeWidth="1.5" points="0,12 15,8 30,14 45,5 60,13 75,9 90,16 105,4 120,12 135,7 150,14 165,6 180,11 200,9" />
        </svg>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {SCORES.map((s, i) => (
          <div key={s} className="fade-up aspect-[9/16] rounded-xl bg-ink p-2 text-paper" style={{ ["--delay" as string]: `${2.4 + i * 0.25}s` }}>
            <div className="font-mono text-[10px] text-paper/80">Clue Score</div>
            <div className="count-up font-mono text-2xl font-bold text-lime" style={{ ["--to" as string]: s, ["--delay" as string]: `${2.4 + i * 0.25}s` }} aria-hidden />
            <span className="sr-only">{s}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-center text-xs text-muted">Illustration of the Auto Clipping flow.</p>
    </div>
  );
}
