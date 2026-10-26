"use client";

import { useEffect, useState } from "react";
import { getSegments } from "@/lib/api/meetings";
import type { Segment } from "@/lib/api/types";

const POLL_INTERVAL_MS = 2000;

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function TranscriptPanel({ meetingId, live }: { meetingId: string; live: boolean }) {
  const [segments, setSegments] = useState<Segment[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const result = await getSegments(meetingId);
        if (cancelled) return;
        setSegments(result);
        setError(false);
      } catch {
        if (!cancelled) setError(true);
      }
    }

    void load();
    if (!live) {
      return () => {
        cancelled = true;
      };
    }
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [meetingId, live]);

  return (
    <section aria-labelledby="transcript-title" className="flex flex-col gap-3">
      <h2 id="transcript-title" className="text-lg font-semibold">
        Transcript
      </h2>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          Cannot load the transcript. Retrying…
        </p>
      )}
      {segments.length === 0 ? (
        <p className="text-sm text-zinc-500">
          {live ? "Waiting for the first segments…" : "No transcript available."}
        </p>
      ) : (
        <ol className="flex flex-col gap-2">
          {segments.map((segment) => (
            <li key={segment.segment_id} className="text-sm">
              <span className="font-medium">{segment.speaker}</span>{" "}
              <span className="text-xs text-zinc-500">{formatTime(segment.start)}</span>
              <p className={segment.is_final ? "" : "text-zinc-500"}>{segment.text}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
