"use client";

import { useAuth } from "./AuthProvider";

/** Who is signed in, and a way out. Nothing is shown when nobody is. */
export function UserMenu() {
  const { user, signOut } = useAuth();
  if (!user) return null;
  return (
    <div className="flex items-center gap-3">
      <span className="hidden text-sm text-muted sm:inline" title={user.email}>
        {user.name}
      </span>
      <button
        type="button"
        onClick={() => void signOut()}
        className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium hover:bg-background"
      >
        Sign out
      </button>
    </div>
  );
}
