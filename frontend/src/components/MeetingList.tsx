"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { errorMessage } from "@/lib/api/client";
import { listMeetings } from "@/lib/api/meetings";
import type { MeetingSummary } from "@/lib/api/types";
import { STATUS_LABELS } from "./StatusBadge";

const LIVE = ["waiting_admission", "capturing", "processing"];

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function formatDuration(seconds: number | null) {
  if (seconds === null) return null;
  return `${Math.max(1, Math.round(seconds / 60))} min`;
}

function meetingState(meeting: MeetingSummary): { label: string; style: string } {
  if (meeting.minutes_status === "validated") {
    return { label: "Validated", style: "bg-brand-soft text-brand-ink" };
  }
  if (meeting.needs_review) {
    return { label: "To review", style: "bg-accent-soft text-accent-ink" };
  }
  if (meeting.status === "failed") {
    return { label: STATUS_LABELS.failed, style: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300" };
  }
  return { label: STATUS_LABELS[meeting.status], style: "bg-background text-muted border border-line" };
}

function Row({ meeting }: { meeting: MeetingSummary }) {
  const state = meetingState(meeting);
  const details = [
    formatDate(meeting.started_at),
    formatDuration(meeting.duration_seconds),
    meeting.participants > 0 ? `${meeting.participants} people` : null,
  ].filter(Boolean);
  const gaps = meeting.counts
    ? meeting.counts.actions_without_owner + meeting.counts.actions_without_deadline
    : 0;
  return (
    <li>
      <Link
        href={`/meetings/${encodeURIComponent(meeting.meeting_id)}`}
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 hover:bg-background sm:px-5"
      >
        <span className="flex min-w-0 flex-col gap-1">
          <span className="truncate font-medium">{meeting.title}</span>
          <span className="text-sm text-muted">
            {details.join(" · ")}
            {meeting.simulated && " · simulated"}
            {meeting.needs_review && gaps > 0 && (
              <span className="text-accent-ink">
                {" "}
                · {gaps} {gaps === 1 ? "item" : "items"} not specified
              </span>
            )}
          </span>
        </span>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${state.style}`}>
          {state.label}
        </span>
      </Link>
    </li>
  );
}

function Group({ title, meetings }: { title: string; meetings: MeetingSummary[] }) {
  if (meetings.length === 0) return null;
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-muted">{title}</h2>
      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {meetings.map((meeting) => (
          <Row key={meeting.meeting_id} meeting={meeting} />
        ))}
      </ul>
    </section>
  );
}

export function MeetingList() {
  const [meetings, setMeetings] = useState<MeetingSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await listMeetings({ limit: 100 });
        if (cancelled) return;
        setMeetings(result.items);
        setError(null);
      } catch (cause) {
        if (!cancelled) setError(errorMessage(cause, "Cannot reach the API."));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  if (error) {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-line bg-surface p-5">
        <p className="text-sm text-red-600 dark:text-red-400">{error} Your meetings are safe: try again.</p>
        <button
          type="button"
          onClick={() => setAttempt((n) => n + 1)}
          className="rounded-lg border border-brand px-3 py-1.5 text-sm font-medium text-brand hover:bg-brand-soft"
        >
          Try again
        </button>
      </div>
    );
  }
  if (meetings === null) {
    return <p className="text-sm text-muted">Loading your meetings…</p>;
  }
  if (meetings.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-xl border border-line bg-surface p-6">
        <h2 className="text-lg font-semibold">Your first meeting will show up here</h2>
        <p className="max-w-lg text-sm text-muted">
          Start the assistant on a Google Meet. When the call ends, the minutes appear here for you
          to review.
        </p>
        <Link
          href="/meetings/new"
          className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-strong"
        >
          Start a meeting capture
        </Link>
      </div>
    );
  }

  const review = meetings.filter((m) => m.needs_review);
  const live = meetings.filter((m) => LIVE.includes(m.status));
  const rest = meetings.filter((m) => !m.needs_review && !LIVE.includes(m.status));
  return (
    <div className="flex flex-col gap-6">
      <Group title="Waiting for your review" meetings={review} />
      <Group title="In progress" meetings={live} />
      <Group title="Recent meetings" meetings={rest} />
    </div>
  );
}
