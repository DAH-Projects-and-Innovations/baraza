import Link from "next/link";
import type { MeetingSummary } from "@/lib/api/types";
import { STATUS_LABELS } from "./StatusBadge";

export const LIVE_STATUSES = ["waiting_admission", "capturing", "processing"];

export function formatDate(iso: string) {
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

export function meetingState(meeting: MeetingSummary): { label: string; className: string } {
  if (meeting.minutes_status === "validated") return { label: "Validated", className: "chip-validated" };
  if (LIVE_STATUSES.slice(0, 2).includes(meeting.status)) return { label: "Live", className: "chip bg-foreground text-white" };
  if (meeting.needs_review) return { label: "Draft", className: "chip-draft" };
  if (meeting.status === "failed") return { label: STATUS_LABELS.failed, className: "chip bg-red-100 text-red-800" };
  return { label: STATUS_LABELS[meeting.status], className: "chip-neutral" };
}

export function MeetingRow({ meeting, roomy = false }: { meeting: MeetingSummary; roomy?: boolean }) {
  const state = meetingState(meeting);
  const details = [
    formatDate(meeting.started_at),
    formatDuration(meeting.duration_seconds),
    meeting.participants > 0 ? `${meeting.participants} people` : null,
    meeting.simulated ? "simulated" : null,
  ].filter(Boolean);
  const gaps = meeting.counts
    ? meeting.counts.actions_without_owner + meeting.counts.actions_without_deadline
    : 0;
  return (
    <li>
      <Link
        href={`/meetings/${encodeURIComponent(meeting.meeting_id)}`}
        className={`flex flex-wrap items-center justify-between gap-4 hover:bg-background ${
          roomy ? "px-7 py-5" : "px-5 py-4"
        }`}
      >
        <span className="flex min-w-0 flex-1 basis-60 flex-col gap-1">
          <span className={`truncate font-serif font-medium ${roomy ? "text-[22px]" : "text-xl"}`}>
            {meeting.title}
          </span>
          <span className="text-sm text-muted">
            {details.join(" · ")}
            {meeting.needs_review && gaps > 0 && (
              <span className="font-semibold text-accent-ink">
                {" "}
                · {gaps} {gaps === 1 ? "item" : "items"} not specified
              </span>
            )}
          </span>
        </span>
        <span className={state.className}>{state.label}</span>
      </Link>
    </li>
  );
}
