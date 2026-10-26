"use client";

import { useEffect, useMemo, useState } from "react";
import { getSegments } from "@/lib/api/meetings";
import type { Segment } from "@/lib/api/types";

const POLL_INTERVAL_MS = 2000;
const UNKNOWN_SPEAKER = /^Speaker \d+$/;

const NAMED_STYLES = [
  "bg-brand-soft text-brand-ink",
  "bg-accent-soft text-accent-ink",
];
const UNKNOWN_STYLE = "bg-background text-muted border border-line";

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function initials(name: string) {
  if (UNKNOWN_SPEAKER.test(name)) return `S${name.split(" ")[1]}`;
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
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

  // Named speakers alternate blue and orange by order of first appearance; unknown speakers stay neutral.
  const styles = useMemo(() => {
    const map = new Map<string, string>();
    for (const { speaker } of segments) {
      if (map.has(speaker)) continue;
      if (UNKNOWN_SPEAKER.test(speaker)) {
        map.set(speaker, UNKNOWN_STYLE);
      } else {
        const named = [...map.values()].filter((v) => v !== UNKNOWN_STYLE).length;
        map.set(speaker, NAMED_STYLES[named % NAMED_STYLES.length]);
      }
    }
    return map;
  }, [segments]);

  return (
    <section
      aria-labelledby="transcript-title"
      className="rounded-xl border border-line bg-surface p-4 sm:p-5"
    >
      <h2 id="transcript-title" className="mb-4 flex items-center gap-2 text-sm font-semibold">
        Transcript
        {live && (
          <span className="rounded-full bg-brand-soft px-2 py-0.5 text-xs font-medium text-brand-ink">
            live
          </span>
        )}
      </h2>
      {error && (
        <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">
          Cannot load the transcript. Retrying…
        </p>
      )}
      {segments.length === 0 ? (
        <p className="text-sm text-muted">
          {live ? "Waiting for the first segments…" : "No transcript available."}
        </p>
      ) : (
        <ol className="flex flex-col gap-4">
          {segments.map((segment) => (
            <li key={segment.segment_id} className="flex gap-3">
              <span
                aria-hidden="true"
                className={`flex h-8 w-8 flex-none items-center justify-center rounded-full text-xs font-semibold ${styles.get(segment.speaker) ?? UNKNOWN_STYLE}`}
              >
                {initials(segment.speaker)}
              </span>
              <div className="min-w-0">
                <p className="text-sm">
                  <span className="font-medium">{segment.speaker}</span>{" "}
                  <span className="text-xs text-faint">{formatTime(segment.start)}</span>
                </p>
                <p className={segment.is_final ? "" : "text-muted"}>{segment.text}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
