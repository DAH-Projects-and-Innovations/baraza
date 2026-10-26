import Link from "next/link";

function LogoMark() {
  return (
    <span
      aria-hidden="true"
      className="flex h-7 w-7 items-center justify-center rounded-md bg-brand text-white"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
      </svg>
    </span>
  );
}

export function Header() {
  return (
    <header className="border-b border-line bg-surface">
      <nav className="mx-auto flex w-full max-w-3xl items-center justify-between px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-base font-semibold">
          <LogoMark />
          Baraza
          <span className="hidden text-xs font-normal text-muted sm:inline">
            by <span className="font-medium text-accent">DAH Labs</span>
          </span>
        </Link>
        <Link
          href="/meetings/new"
          className="rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-strong"
        >
          New meeting
        </Link>
      </nav>
    </header>
  );
}
