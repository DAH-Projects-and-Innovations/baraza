"use client";

import { useEffect, useState } from "react";
import { getCaptureStatus, stopCapture } from "@/lib/api/captures";
import type { CaptureStatus } from "@/lib/api/types";

const POLL_INTERVAL_MS = 2000;

const LABELS: Record<CaptureStatus, string> = {
  waiting_admission: "Waiting to be admitted to the meeting",
  capturing: "Capturing the meeting",
  processing: "Processing the transcript",
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
    <div className="flex flex-col gap-4">
      <p className="text-xs text-zinc-500">
        Capture <code>{captureId}</code>
      </p>
      <p role="status" aria-live="polite" className="text-lg font-medium">
        {status ? LABELS[status] : "Loading status…"}
      </p>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
      {canStop && (
        <button
          type="button"
          onClick={onStop}
          disabled={stopping}
          className="self-start rounded-md border border-red-600 px-4 py-2 text-sm text-red-600 disabled:opacity-50"
        >
          {stopping ? "Stopping…" : "Stop capture"}
        </button>
      )}
    </div>
  );
}
