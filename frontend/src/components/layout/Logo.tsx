export function WaveIcon({ size = 19 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
      <path d="M5 10v4M9 6v12M13 9v6M17 4v16M21 11v2" />
    </svg>
  );
}

/** The brand mark: a waveform on the blue to violet gradient. */
export function Logo({ size = 34, textClass = "text-[22px]" }: { size?: number; textClass?: string }) {
  return (
    <span className="flex items-center gap-2.5">
      <span
        className="inline-flex flex-none items-center justify-center rounded-[11px] bg-gradient-to-br from-brand to-violet"
        style={{ width: size, height: size }}
      >
        <WaveIcon size={Math.round(size * 0.56)} />
      </span>
      <span className={`font-display font-extrabold tracking-[-0.02em] ${textClass}`}>Baraza</span>
    </span>
  );
}
