"use client";

import { useEffect, useState, type FormEvent } from "react";
import { changePassword } from "@/lib/api/auth";
import { getBotName } from "@/lib/api/captures";
import { ApiError, errorMessage } from "@/lib/api/client";
import { waitMessage } from "@/lib/auth";
import { USE_MOCK_API } from "@/lib/config";
import { useAuth } from "./AuthProvider";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[13px] font-semibold text-muted">{label}</span>
      <span className="text-base">{value}</span>
    </div>
  );
}

function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (!current || !next) {
      setError("Enter your current password and a new one.");
      return;
    }
    setPending(true);
    setError(null);
    setDone(false);
    try {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setDone(true);
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 429
          ? waitMessage(cause.retryAfter)
          : errorMessage(cause, "Could not change the password. Try again."),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <label className="flex flex-col gap-2 text-sm font-semibold">
        Current password
        <input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} className="field" />
      </label>
      <label className="flex flex-col gap-2 text-sm font-semibold">
        New password
        <input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} className="field" />
      </label>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {done && <p role="status" className="text-sm font-semibold text-brand-ink">Password changed.</p>}
      <button type="submit" disabled={pending} className="btn btn-dark self-start">
        {pending ? "Saving…" : "Change password"}
      </button>
    </form>
  );
}

export function SettingsView() {
  const { user } = useAuth();
  const [botName, setBotName] = useState<string | null>(null);

  useEffect(() => {
    getBotName().then(setBotName).catch(() => undefined);
  }, []);

  return (
    <>
      <section className="card flex flex-col gap-5 px-8 py-7">
        <h2 className="font-display text-lg font-bold">Account</h2>
        {user && (
          <div className="grid gap-5 sm:grid-cols-2">
            <Row label="Name" value={user.name} />
            <Row label="Work email" value={user.email} />
          </div>
        )}
      </section>

      {!USE_MOCK_API && (
        <section className="card flex flex-col gap-5 px-8 py-7">
          <h2 className="font-display text-lg font-bold">Password</h2>
          <PasswordForm />
        </section>
      )}

      <section className="card flex flex-col gap-3.5 px-8 py-7">
        <h2 className="font-display text-lg font-bold">The assistant</h2>
        <p className="text-[15px] leading-relaxed text-secondary">
          The assistant always joins as a visible participant
          {botName ? <> named <strong>{botName}</strong></> : null}. Tell the participants before you
          start: it cannot post a notice in the meeting chat. Nothing is shared until a person validates
          the minutes.
        </p>
      </section>
    </>
  );
}
