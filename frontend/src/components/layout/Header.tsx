import Link from "next/link";

export function Header() {
  return (
    <header className="border-b border-zinc-200 dark:border-zinc-800">
      <nav className="mx-auto flex w-full max-w-3xl items-center justify-between px-6 py-4">
        <Link href="/" className="font-semibold tracking-tight">
          Baraza
        </Link>
        <Link href="/meetings/new" className="text-sm text-zinc-600 dark:text-zinc-400">
          New meeting
        </Link>
      </nav>
    </header>
  );
}
