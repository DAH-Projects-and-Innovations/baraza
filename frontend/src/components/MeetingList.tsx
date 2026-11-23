"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { errorMessage } from "@/lib/api/client";
import { listMeetings } from "@/lib/api/meetings";
import type { MeetingSummary } from "@/lib/api/types";
import { MeetingRow } from "./MeetingRow";

type Filter = "all" | "drafts" | "validated" | "month";

/** Loads the meetings once, with a retry that does not lose anything. */
export function useMeetings() {
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

  return { meetings, error, retry: () => setAttempt((n) => n + 1) };
}

export function LoadError({ error, retry }: { error: string; retry: () => void }) {
  return (
    <div role="alert" className="card flex flex-col items-start gap-3 p-6">
      <p className="text-sm text-red-700">{error} Your meetings are safe: try again.</p>
      <button type="button" onClick={retry} className="btn btn-secondary">
        Try again
      </button>
    </div>
  );
}

export function EmptyMeetings() {
  return (
    <div className="card flex flex-col items-start gap-3 p-8">
      <h2 className="font-display text-xl font-bold">Your first meeting will show up here</h2>
      <p className="max-w-lg text-[15px] leading-relaxed text-secondary">
        Start the assistant on a Google Meet. When the call ends, the minutes appear here for you
        to review.
      </p>
      <Link href="/meetings/new" className="btn btn-primary">
        Start a meeting capture
      </Link>
    </div>
  );
}

function PillButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full px-4 py-2 text-sm font-semibold ${
        active ? "bg-foreground text-white" : "border border-[#d7dbe8] bg-surface text-secondary hover:bg-background"
      }`}
    >
      {children}
    </button>
  );
}

/** The meetings page: search by title and a few filters. */
export function MeetingLibrary() {
  const { meetings, error, retry } = useMeetings();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const drafts = useMemo(() => (meetings ?? []).filter((m) => m.minutes_status !== "validated").length, [meetings]);

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const now = new Date();
    return (meetings ?? []).filter((m) => {
      if (needle && !m.title.toLowerCase().includes(needle)) return false;
      if (filter === "drafts") return m.minutes_status !== "validated";
      if (filter === "validated") return m.minutes_status === "validated";
      if (filter === "month") {
        const started = new Date(m.started_at);
        return started.getMonth() === now.getMonth() && started.getFullYear() === now.getFullYear();
      }
      return true;
    });
  }, [meetings, query, filter]);

  if (error) return <LoadError error={error} retry={retry} />;
  if (meetings === null) return <p className="text-sm text-muted">Loading your meetings…</p>;
  if (meetings.length === 0) return <EmptyMeetings />;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex min-h-12 flex-1 basis-80 items-center gap-2.5 rounded-[14px] border border-[#d7dbe8] bg-surface px-4">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#5f667a" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" />
            <path d="M16 16l4 4" />
          </svg>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search meetings by title"
            aria-label="Search meetings"
            className="min-w-0 flex-1 bg-transparent text-[15px] outline-none"
          />
        </label>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter meetings">
          <PillButton active={filter === "all"} onClick={() => setFilter("all")}>All</PillButton>
          <PillButton active={filter === "drafts"} onClick={() => setFilter("drafts")}>
            Drafts{drafts > 0 ? ` · ${drafts}` : ""}
          </PillButton>
          <PillButton active={filter === "validated"} onClick={() => setFilter("validated")}>Validated</PillButton>
          <PillButton active={filter === "month"} onClick={() => setFilter("month")}>This month</PillButton>
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="card p-6 text-[15px] text-muted">No meeting matches. Try another word or filter.</p>
      ) : (
        <ul className="card divide-y divide-line overflow-hidden">
          {shown.map((meeting) => (
            <MeetingRow key={meeting.meeting_id} meeting={meeting} roomy />
          ))}
        </ul>
      )}
    </div>
  );
}
