"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { USE_MOCK_API } from "@/lib/config";
import { useAuth } from "../AuthProvider";
import { Logo } from "./Logo";

const ICONS = {
  home: <path d="M4 11l8-7 8 7v9H4z" />,
  meetings: (
    <>
      <rect x="4" y="5" width="16" height="15" rx="3" />
      <path d="M4 10h16M9 3v4M15 3v4" />
    </>
  ),
  actions: <path d="M5 6l2 2 3-3M5 14l2 2 3-3M13 7h7M13 15h7" />,
  settings: <path d="M4 7h10M18 7h2M4 17h2M10 17h10M16 5v4M8 15v4" />,
};

const LINKS: { href: string; label: string; icon: keyof typeof ICONS }[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/meetings", label: "Meetings", icon: "meetings" },
  { href: "/actions", label: "Actions", icon: "actions" },
  { href: "/settings", label: "Settings", icon: "settings" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/meetings") return pathname === "/meetings" || /^\/meetings\/(?!new)/.test(pathname);
  return pathname.startsWith(href);
}

function initials(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "?"
  );
}

function Sidebar() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  return (
    <nav
      aria-label="Main"
      className="flex flex-none items-center gap-1 overflow-x-auto border-b border-line bg-surface px-2.5 py-2 md:sticky md:top-0 md:h-screen md:w-54 md:flex-col md:items-stretch md:gap-0.5 md:overflow-visible md:border-b-0 md:bg-transparent md:px-3 md:py-6"
    >
      <Link href="/" className="flex-none px-3 md:pb-6 md:pt-1">
        <Logo />
      </Link>
      {LINKS.map((link) => {
        const active = isActive(pathname, link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`flex min-h-11 flex-none items-center gap-3 rounded-xl px-3 text-[15px] whitespace-nowrap ${
              active ? "bg-brand-soft font-semibold text-brand-ink" : "font-medium text-secondary hover:bg-surface"
            } ${link.href === "/settings" ? "md:mt-3" : ""}`}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              {ICONS[link.icon]}
            </svg>
            {link.label}
          </Link>
        );
      })}
      {user && (
        <div className="hidden items-center gap-2.5 px-3 py-2 md:mt-auto md:flex">
          <span className="inline-flex h-9 w-9 flex-none items-center justify-center rounded-full bg-brand-soft text-[13px] font-bold text-brand-ink">
            {initials(user.name)}
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-semibold" title={user.email}>
              {user.name}
            </span>
            <button type="button" onClick={() => void signOut()} className="text-left text-xs text-muted hover:text-foreground">
              Sign out
            </button>
          </span>
        </div>
      )}
      {user && (
        <button type="button" onClick={() => void signOut()} className="ml-auto flex-none px-3 text-sm font-medium whitespace-nowrap text-muted md:hidden">
          Sign out
        </button>
      )}
    </nav>
  );
}

/** The signed in frame: a sidebar and the page. The sign in page stands on its own. */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login") return <>{children}</>;
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        {USE_MOCK_API && (
          <p role="status" className="bg-accent-soft px-4 py-2 text-center text-sm text-accent-ink">
            Browser simulation: fictional transcript and minutes. No bot joins Google Meet.
          </p>
        )}
        <main className="flex flex-1 flex-col">{children}</main>
      </div>
    </div>
  );
}
