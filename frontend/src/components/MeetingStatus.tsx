"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getCaptureStatus, retryGeneration, stopCapture } from "@/lib/api/captures";
import { ApiError, errorMessage } from "@/lib/api/client";
import type { CaptureStatus, CaptureStatusResponse } from "@/lib/api/types";
import { MinutesPanel } from "./MinutesPanel";
import { TranscriptPanel } from "./TranscriptPanel";

const POLL_INTERVAL_MS = 2000;

const LABELS: Record<CaptureStatus, string> = {
  waiting_admission: "Waiting to be admitted",
  capturing: "Capturing",
  processing: "Processing",
  done: "Draft ready",
  failed: "Capture failed",
};

const FINAL: CaptureStatus[] = ["done", "failed"];

export function MeetingStatus({ captureId }: { captureId: string }) {
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [details, setDetails] = useState<CaptureStatusResponse | null>(null);
  const [missing, setMissing] = useState(false);

  const isFinal = missing || (status !== null && FINAL.includes(status));
  const meetingId = details?.meeting_id ?? captureId;

  useEffect(() => {
    if (isFinal) return;
    let cancelled = false;
    let loading = false;

    async function poll() {
      if (loading) return;
      loading = true;
      try {
        const result = await getCaptureStatus(captureId);
        if (cancelled) return;
        setStatus(result.status);
        setDetails(result);
        setError(null);
      } catch (error) {
        if (!cancelled) {
          setMissing(error instanceof ApiError && error.status === 404);
          setError(errorMessage(error, "Cannot reach the API. Retrying…"));
        }
      } finally {
        loading = false;
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
      const result = await stopCapture(captureId);
      setStatus(result?.status ?? "processing");
      if (result) setDetails(result);
      setError(null);
    } catch (error) {
      setError(errorMessage(error, "Could not stop the capture. Try again."));
    } finally {
      setStopping(false);
    }
  }

  const canStop = !details?.stop_requested && (status === "waiting_admission" || status === "capturing");

  async function onRetry() {
    setStopping(true);
    try {
      await retryGeneration(meetingId);
      setStatus("processing");
      setDetails((current) => current ? { ...current, error: null, can_retry: false } : current);
      setError(null);
    } catch (error) {
      setError(errorMessage(error, "Could not restart generation. Try again."));
    } finally {
      setStopping(false);
    }
  }

  if (missing) return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Meeting not found</h1>
      <p role="alert">This meeting is unavailable. Check the link or start a new capture.</p>
      <Link href="/meetings/new" className="text-brand underline">New meeting</Link>
    </div>
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{details?.title ?? "Meeting"}</h1>
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
      {details?.simulated && (
        <p className="rounded-lg bg-accent-soft p-3 text-sm text-accent-ink">
          Simulated capture: no bot joins Meet. The transcript is fictional.
        </p>
      )}
      {details?.phase && <p role="status" className="text-sm text-muted">{details.phase}</p>}
      {details?.stop_requested && status !== "done" && status !== "failed" && (
        <p role="status" className="text-sm text-muted">Stop requested. Waiting for the final transcript and draft.</p>
      )}
      {details?.error && <p role="alert" className="text-sm text-red-600">{details.error}</p>}
      {status === "failed" && (
        details?.can_retry ? (
          <button onClick={onRetry} disabled={stopping} className="self-start rounded-lg border border-brand px-3 py-2 text-brand disabled:opacity-60">
            {stopping ? "Retrying…" : "Retry generation"}
          </button>
        ) : <Link href="/meetings/new" className="text-brand underline">Start a new capture</Link>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <TranscriptPanel meetingId={meetingId} live={status === "waiting_admission" || status === "capturing"} />
      <MinutesPanel meetingId={meetingId} ready={status === "processing" || status === "done"} />
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
