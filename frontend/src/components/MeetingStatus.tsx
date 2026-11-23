"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getCaptureStatus, retryGeneration, stopCapture } from "@/lib/api/captures";
import { ApiError, errorMessage } from "@/lib/api/client";
import type { CaptureStatus, CaptureStatusResponse } from "@/lib/api/types";
import { MinutesPanel } from "./MinutesPanel";
import { StatusBadge } from "./StatusBadge";
import { TranscriptPanel } from "./TranscriptPanel";

const POLL_INTERVAL_MS = 2000;

const FINAL: CaptureStatus[] = ["done", "failed"];

export function MeetingStatus({ captureId }: { captureId: string }) {
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [details, setDetails] = useState<CaptureStatusResponse | null>(null);
  const [missing, setMissing] = useState(false);
  // Bumped when a speaker is named: the minutes then pick up the new owners.
  const [minutesReload, setMinutesReload] = useState(0);

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
    <div className="card flex max-w-lg flex-col items-start gap-4 p-8">
      <h1 className="font-display text-2xl font-extrabold">Meeting not found</h1>
      <p role="alert" className="text-[15px] text-secondary">This meeting is unavailable. Check the link or start a new capture.</p>
      <Link href="/meetings/new" className="btn btn-primary">New meeting</Link>
    </div>
  );

  const title = details?.title ?? "Meeting";
  const live = status === "waiting_admission" || status === "capturing";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/meetings" className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 6l-6 6 6 6" />
          </svg>
          Meetings
        </Link>
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          {canStop && (
            <button type="button" onClick={onStop} disabled={stopping} className="btn btn-secondary min-h-10 border-accent px-4 text-sm text-accent-ink">
              {stopping ? "Stopping…" : "Stop capture"}
            </button>
          )}
        </div>
      </div>
      {live && (
        <h1 className="font-serif text-4xl leading-tight font-medium">{title}</h1>
      )}
      {details?.simulated && (
        <p className="rounded-xl border border-accent-line bg-accent-soft p-3 text-sm text-accent-ink">
          Simulated capture: no bot joins Meet. The transcript is fictional.
        </p>
      )}
      {details?.phase && <p role="status" className="text-sm text-muted">{details.phase}</p>}
      {details?.stop_requested && status !== "done" && status !== "failed" && (
        <p role="status" className="text-sm text-muted">Stop requested. Waiting for the final transcript and draft.</p>
      )}
      {details?.error && <p role="alert" className="text-sm text-red-700">{details.error}</p>}
      {status === "failed" && (
        details?.can_retry ? (
          <button onClick={onRetry} disabled={stopping} className="btn btn-secondary self-start">
            {stopping ? "Retrying…" : "Retry generation"}
          </button>
        ) : <Link href="/meetings/new" className="btn btn-primary self-start">Start a new capture</Link>
      )}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {live ? (
        <TranscriptPanel
          meetingId={meetingId}
          live
          onSpeakerRenamed={() => setMinutesReload((n) => n + 1)}
        />
      ) : (
        <>
          <MinutesPanel
            meetingId={meetingId}
            ready={status === "processing" || status === "done"}
            title={title}
            meta={`Capture ${captureId}`}
            reloadKey={minutesReload}
          />
          <TranscriptPanel
            meetingId={meetingId}
            live={false}
            onSpeakerRenamed={() => setMinutesReload((n) => n + 1)}
          />
        </>
      )}
    </div>
  );
}
