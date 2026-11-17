"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getCurrentUser, signOut as apiSignOut, type User } from "@/lib/api/auth";
import { SIGNED_OUT_EVENT, errorMessage } from "@/lib/api/client";
import { loginUrl } from "@/lib/auth";

interface AuthState {
  user: User | null;
  /** False until the first answer about the session has arrived. */
  checked: boolean;
  /** Set when the API cannot be reached, which is not the same as "not signed in". */
  problem: string | null;
  retry: () => void;
  signOut: () => Promise<void>;
  /** Called after a successful sign in so the header and the pages know who is here. */
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

/** Knows who is signed in, and ends the session when the API says it is over. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const current = await getCurrentUser();
        if (cancelled) return;
        setUser(current);
        setProblem(null);
      } catch (error) {
        if (!cancelled) setProblem(errorMessage(error, "Cannot reach the API."));
      } finally {
        if (!cancelled) setChecked(true);
      }
    }
    void check();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  // The API ended the session while the person was on a page.
  useEffect(() => {
    function ended() {
      setUser(null);
    }
    window.addEventListener(SIGNED_OUT_EVENT, ended);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, ended);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await apiSignOut();
    } finally {
      setUser(null);
      router.replace("/login");
    }
  }, [router]);

  const retry = useCallback(() => {
    setChecked(false);
    setAttempt((n) => n + 1);
  }, []);

  return (
    <AuthContext.Provider value={{ user, checked, problem, retry, signOut, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

/** Shows the page only to a signed in person. The sign in page is always open. */
export function AuthGate({ children }: { children: ReactNode }) {
  const { user, checked, problem, retry } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const onLoginPage = pathname === "/login";
  const needsSignIn = checked && !problem && user === null && !onLoginPage;

  useEffect(() => {
    if (needsSignIn) router.replace(loginUrl(window.location.pathname + window.location.search));
  }, [needsSignIn, router]);

  if (onLoginPage) return <>{children}</>;
  if (!checked) return <p className="px-4 py-10 text-center text-sm text-muted">Loading…</p>;
  if (problem) {
    return (
      <div role="alert" className="mx-auto flex max-w-md flex-col items-center gap-3 px-4 py-16 text-center">
        <p className="text-sm text-red-600 dark:text-red-400">{problem}</p>
        <button
          type="button"
          onClick={retry}
          className="rounded-lg border border-brand px-3 py-1.5 text-sm font-medium text-brand hover:bg-brand-soft"
        >
          Try again
        </button>
      </div>
    );
  }
  if (user === null) {
    return <p className="px-4 py-10 text-center text-sm text-muted">Redirecting to sign in…</p>;
  }
  return <>{children}</>;
}
