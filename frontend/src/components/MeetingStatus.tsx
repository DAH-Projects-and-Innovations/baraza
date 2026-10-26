"use client";

import { useEffect, useState } from "react";
import { getCaptureStatus, stopCapture } from "@/lib/api/captures";
import type { CaptureStatus } from "@/lib/api/types";
import { MinutesPanel } from "./MinutesPanel";
import { TranscriptPanel } from "./TranscriptPanel";

const POLL_INTERVAL_MS = 2000;

const LABELS: Record<CaptureStatus, string> = {
  waiting_admission: "Waiting to be admitted",
  capturing: "Capturing",
  processing: "Processing",
  done: "Capture complete",
  failed: "Capture failed",
};

const FINAL: CaptureStatus[] = ["done", "failed"];

export function MeetingStatus({ captureId }: { captureId: string }) {
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  const isFinal = status !== null && FINAL.includes(status);

  useEffect(() => {
    if (isFinal) return;
    let cancelled = false;

    async function poll() {
      try {
        const result = await getCaptureStatus(captureId);
        if (cancelled) return;
        setStatus(result.status);
        setError(null);
      } catch {
        if (!cancelled) setError("Cannot reach the API. Retrying…");
      }
    }

    void poll();
    const timer = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [captureId, isFinal]);

  async function onStop() {
    setStopping(true);
    try {
      await stopCapture(captureId);
      setStatus("processing");
      setError(null);
    } catch {
      setError("Could not stop the capture. Try again.");
    } finally {
      setStopping(false);
    }
  }

  const canStop = status === "waiting_admission" || status === "capturing";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Meeting</h1>
          <p className="text-xs text-muted">
            Capture <code>{captureId}</code>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          {canStop && (
            <button
              type="button"
              onClick={onStop}
              disabled={stopping}
              className="rounded-lg border border-accent px-3 py-1.5 text-sm font-medium text-accent-strong hover:bg-accent-soft disabled:opacity-60"
            >
              {stopping ? "Stopping…" : "Stop capture"}
            </button>
          )}
        </div>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <TranscriptPanel meetingId={captureId} live={status !== null && !isFinal} />
      <MinutesPanel meetingId={captureId} ready={status === "done"} />
    </div>
  );
}

const BADGE_STYLES: Record<CaptureStatus, string> = {
  waiting_admission: "bg-accent-soft text-accent-ink",
  capturing: "bg-brand-soft text-brand-ink",
  processing: "bg-accent-soft text-accent-ink",
  done: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};

function StatusBadge({ status }: { status: CaptureStatus | null }) {
  if (!status) {
    return <span className="text-sm text-muted">Loading status…</span>;
  }
  const pulsing = status === "capturing" || status === "waiting_admission" || status === "processing";
  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ${BADGE_STYLES[status]}`}
    >
      <span
        aria-hidden="true"
        className={`h-2 w-2 rounded-full bg-current ${pulsing ? "animate-pulse" : ""}`}
      />
      {LABELS[status]}
    </span>
  );
}
