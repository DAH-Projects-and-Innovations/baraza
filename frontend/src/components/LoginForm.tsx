"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { signIn } from "@/lib/api/auth";
import { ApiError, errorMessage } from "@/lib/api/client";
import { safeNext, waitMessage } from "@/lib/auth";
import { USE_MOCK_API } from "@/lib/config";
import { useAuth } from "./AuthProvider";

const INPUT =
  "w-full rounded-lg border border-line bg-background px-3 py-2.5 text-base text-foreground";

export function LoginForm() {
  const router = useRouter();
  const { user, checked, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  // Someone who is already signed in has nothing to do here.
  useEffect(() => {
    if (checked && user) {
      router.replace(safeNext(new URLSearchParams(window.location.search).get("next")));
    }
  }, [checked, user, router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (!email.trim() || !password) {
      setError("Enter your email and your password.");
      return;
    }
    setError(null);
    setPending(true);
    try {
      const person = await signIn(email, password);
      setUser(person);
      router.replace(safeNext(new URLSearchParams(window.location.search).get("next")));
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 429) {
        setError(waitMessage(cause.retryAfter));
      } else {
        setError(errorMessage(cause, "Cannot reach the API. Check your connection and try again."));
      }
      setPending(false);
    }
  }

  if (USE_MOCK_API) {
    return (
      <p className="rounded-lg bg-accent-soft p-3 text-sm text-accent-ink">
        The browser simulation has no accounts. Open the app from the home page.
      </p>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        Work email
        <input
          type="email"
          name="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className={INPUT}
        />
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        Password
        <span className="flex items-center rounded-lg border border-line bg-background pr-1">
          <input
            type={showPassword ? "text" : "password"}
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="min-w-0 flex-1 bg-transparent px-3 py-2.5 text-base text-foreground outline-none"
          />
          <button
            type="button"
            onClick={() => setShowPassword((shown) => !shown)}
            aria-pressed={showPassword}
            className="min-h-11 min-w-14 rounded-md px-2 text-sm font-medium text-brand"
          >
            {showPassword ? "Hide" : "Show"}
          </button>
        </span>
      </label>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="min-h-12 rounded-lg bg-brand px-4 py-2.5 text-base font-medium text-white hover:bg-brand-strong disabled:opacity-60"
      >
        {pending ? "Signing in…" : "Sign in"}
      </button>
      <p className="text-sm text-muted">
        There is no public sign up yet. Ask the person who runs Baraza for your account.
      </p>
    </form>
  );
}
