export function Logo({ size = 32 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2 font-display text-xl font-bold">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/icon.svg" alt="" width={size} height={size} />
      <span>
        clue<span className="text-violet"> AI</span>
      </span>
    </span>
  );
}
