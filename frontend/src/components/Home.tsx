"use client";

import Link from "next/link";
import { useAuth } from "./AuthProvider";
import { WaveIcon } from "./layout/Logo";
import { EmptyMeetings, LoadError, useMeetings } from "./MeetingList";
import { LIVE_STATUSES, MeetingRow } from "./MeetingRow";

function greeting(hour: number) {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function Stat({ label, value, warn = false }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className="flex flex-col gap-1 rounded-[20px] border border-line bg-surface px-6 py-5">
      <span className="text-sm text-muted">{label}</span>
      <span className={`font-display text-4xl font-extrabold tracking-[-0.02em] ${warn ? "text-accent-ink" : ""}`}>
        {value}
      </span>
    </div>
  );
}

export function Home() {
  const { user } = useAuth();
  const { meetings, error, retry } = useMeetings();
  const now = new Date();
  const first = user?.name.split(/\s+/)[0];
  const today = now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });

  const review = meetings?.find((m) => m.needs_review) ?? null;
  const reviewCount = meetings?.filter((m) => m.needs_review).length ?? 0;
  const live = meetings?.find((m) => LIVE_STATUSES.slice(0, 2).includes(m.status)) ?? null;
  const thisMonth =
    meetings?.filter((m) => {
      const d = new Date(m.started_at);
      return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
    }).length ?? 0;
  const decisions =
    meetings?.reduce((sum, m) => sum + (m.minutes_status === "validated" ? (m.counts?.decisions ?? 0) : 0), 0) ?? 0;

  return (
    <div className="flex flex-col gap-8 px-5 py-8 md:px-14 md:py-10">
      <header className="flex flex-col gap-1.5">
        <span className="text-sm text-muted">{today}</span>
        <h1 className="font-display text-4xl leading-[1.1] font-extrabold tracking-[-0.025em] md:text-[40px]">
          {greeting(now.getHours())}
          {first ? `, ${first}` : ""}
        </h1>
      </header>

      <section aria-labelledby="bot" className="relative flex flex-wrap items-center gap-6 overflow-hidden rounded-[28px] bg-navy p-8 text-white">
        <span aria-hidden="true" className="absolute -top-44 -right-28 h-105 w-105 rounded-full bg-[radial-gradient(circle,rgba(91,63,240,0.5),rgba(91,63,240,0)_70%)]" />
        <span className="relative inline-flex h-16 w-16 flex-none items-center justify-center rounded-full bg-gradient-to-br from-brand to-violet shadow-[0_0_0_8px_rgba(124,166,255,0.14)]">
          <WaveIcon size={30} />
        </span>
        <div className="relative flex flex-1 basis-70 flex-col gap-2">
          <h2 id="bot" className="font-display text-[26px] font-bold tracking-[-0.015em]">
            {live ? "Your assistant is in a meeting" : "Your assistant is ready"}
          </h2>
          <span className="text-[15px] leading-relaxed text-[#c3cdf0]">
            {live
              ? `${live.title} is being transcribed. The minutes appear here when the call ends.`
              : "Paste a Google Meet link to send the assistant. The minutes appear here when the call ends."}
          </span>
        </div>
        <Link
          href={live ? `/meetings/${encodeURIComponent(live.meeting_id)}` : "/meetings/new"}
          className="btn relative bg-white text-navy hover:bg-brand-soft"
        >
          {live ? "Follow the meeting" : "Start a meeting capture"}
        </Link>
      </section>

      {error ? (
        <LoadError error={error} retry={retry} />
      ) : meetings === null ? (
        <p className="text-sm text-muted">Loading your meetings…</p>
      ) : meetings.length === 0 ? (
        <EmptyMeetings />
      ) : (
        <>
          {review && (
            <section aria-labelledby="rev" className="flex flex-wrap items-center justify-between gap-5 rounded-3xl border border-accent-line bg-surface px-8 py-7 shadow-[0_8px_24px_rgba(255,122,47,0.1)]">
              <div className="flex flex-1 basis-80 flex-col gap-2">
                <span className="inline-flex items-center gap-2 text-[13px] font-semibold text-accent-ink">
                  <span className="h-2 w-2 rounded-full bg-accent" />
                  Waiting for your review{reviewCount > 1 ? ` · ${reviewCount} meetings` : ""}
                </span>
                <h2 id="rev" className="font-serif text-[30px] leading-tight font-medium">{review.title}</h2>
                {review.counts && (
                  <span className="text-[15px] leading-normal text-secondary">
                    {review.counts.decisions} decisions and {review.counts.actions} actions drafted.
                    {review.counts.actions_without_owner + review.counts.actions_without_deadline > 0 &&
                      ` ${review.counts.actions_without_owner + review.counts.actions_without_deadline} gaps to fill in.`}
                  </span>
                )}
              </div>
              <Link href={`/meetings/${encodeURIComponent(review.meeting_id)}`} className="btn btn-dark min-h-13 px-6.5">
                Review the minutes
              </Link>
            </section>
          )}

          <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
            <Stat label="Meetings this month" value={thisMonth} />
            <Stat label="Decisions recorded" value={decisions} />
            <Stat label="Waiting for review" value={reviewCount} warn={reviewCount > 0} />
          </div>

          <section aria-labelledby="rec" className="flex flex-col gap-3">
            <div className="flex items-baseline justify-between">
              <h2 id="rec" className="font-display text-lg font-bold">Recent meetings</h2>
              <Link href="/meetings" className="text-sm font-semibold text-brand">All meetings</Link>
            </div>
            <ul className="divide-y divide-line overflow-hidden rounded-[20px] border border-line bg-surface">
              {meetings.slice(0, 5).map((m) => (
                <MeetingRow key={m.meeting_id} meeting={m} />
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
