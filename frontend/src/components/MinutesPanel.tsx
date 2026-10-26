"use client";

import { useEffect, useState, type ReactNode } from "react";
import { getMinutes } from "@/lib/api/meetings";
import type { Minutes } from "@/lib/api/types";

const NOT_SPECIFIED = "Not specified";
const POLL_INTERVAL_MS = 3000;

export function MinutesPanel({ meetingId, ready }: { meetingId: string; ready: boolean }) {
  const [minutes, setMinutes] = useState<Minutes | null>(null);
  const [error, setError] = useState(false);
  const loaded = minutes !== null;

  useEffect(() => {
    if (!ready || loaded) return;
    let cancelled = false;

    async function load() {
      try {
        const result = await getMinutes(meetingId);
        if (cancelled) return;
        setMinutes(result);
        setError(false);
      } catch {
        if (!cancelled) setError(true);
      }
    }

    // Minutes can take a while to generate: poll until they exist.
    void load();
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [meetingId, ready, loaded]);

  if (!ready) return null;

  return (
    <section aria-labelledby="minutes-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="minutes-title" className="text-lg font-semibold tracking-tight">
          Minutes
        </h2>
        <span className="rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-ink">
          AI draft, to review
        </span>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          Cannot load the minutes. Retrying…
        </p>
      )}
      {!minutes ? (
        <p className="rounded-xl border border-line bg-surface p-4 text-sm text-muted">
          Generating the minutes…
        </p>
      ) : (
        <>
          <Card title="Summary">
            <p>{minutes.summary}</p>
          </Card>
          {minutes.topics.length > 0 && (
            <Card title="Topics">
              <ul className="flex flex-col gap-2">
                {minutes.topics.map((t) => (
                  <li key={t.title}>
                    <span className="font-medium">{t.title}</span>
                    <span className="text-muted"> — {t.summary}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Card title="Decisions" tone="brand">
              {minutes.decisions.length === 0 ? (
                <Missing />
              ) : (
                <ul className="flex flex-col gap-2">
                  {minutes.decisions.map((d) => (
                    <li key={d.text}>{d.text}</li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title="Actions" tone="accent">
              {minutes.actions.length === 0 ? (
                <Missing />
              ) : (
                <ul className="flex flex-col gap-3">
                  {minutes.actions.map((a) => (
                    <li key={a.text}>
                      <p>{a.text}</p>
                      <p className="text-xs text-muted">
                        <Field label="Owner" value={a.owner} /> · <Field label="Due" value={a.due_date} />
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
          <Card title="Open points">
            {minutes.open_points.length === 0 ? (
              <Missing />
            ) : (
              <ul className="flex flex-col gap-2">
                {minutes.open_points.map((p) => (
                  <li key={p.text}>{p.text}</li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </section>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return value ? (
    <span>
      {label}: <span className="text-foreground">{value}</span>
    </span>
  ) : (
    <span className="italic text-faint">
      {label}: {NOT_SPECIFIED.toLowerCase()}
    </span>
  );
}

function Missing() {
  return <p className="italic text-faint">{NOT_SPECIFIED}</p>;
}

function Card({
  title,
  tone,
  children,
}: {
  title: string;
  tone?: "brand" | "accent";
  children: ReactNode;
}) {
  const titleColor =
    tone === "brand" ? "text-brand-ink" : tone === "accent" ? "text-accent-ink" : "text-muted";
  return (
    <div className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <h3 className={`mb-2 text-xs font-semibold uppercase tracking-wide ${titleColor}`}>{title}</h3>
      {children}
    </div>
  );
}
