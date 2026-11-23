import type { CaptureStatus } from "@/lib/api/types";

export const STATUS_LABELS: Record<CaptureStatus, string> = {
  waiting_admission: "Waiting to be admitted",
  capturing: "Capturing",
  processing: "Processing",
  done: "Draft ready",
  failed: "Capture failed",
};

const BADGE_STYLES: Record<CaptureStatus, string> = {
  waiting_admission: "bg-accent-soft text-accent-ink",
  capturing: "bg-foreground text-white",
  processing: "bg-accent-soft text-accent-ink",
  done: "bg-brand-soft text-brand-ink",
  failed: "bg-red-100 text-red-800",
};

export function StatusBadge({ status }: { status: CaptureStatus | null }) {
  if (!status) {
    return <span className="text-sm text-muted">Loading status…</span>;
  }
  const pulsing = status === "capturing" || status === "waiting_admission" || status === "processing";
  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[13px] font-semibold ${BADGE_STYLES[status]}`}
    >
      <span
        aria-hidden="true"
        className={`h-1.75 w-1.75 rounded-full ${status === "capturing" ? "bg-accent" : "bg-current"} ${pulsing ? "animate-pulse" : ""}`}
      />
      {STATUS_LABELS[status]}
    </span>
  );
}
