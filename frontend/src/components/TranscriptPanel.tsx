"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "@/lib/api/client";
import { REVIEW_AVAILABLE, getSegments, renameSpeaker } from "@/lib/api/meetings";
import type { Segment } from "@/lib/api/types";
import { isUnnamedSpeaker, knownNames, tidyName } from "@/lib/speakers";

const POLL_INTERVAL_MS = 2000;

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
  if (isUnnamedSpeaker(name)) return `S${name.split(" ")[1]}`;
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function TranscriptPanel({
  meetingId,
  live,
  onSpeakerRenamed,
}: {
  meetingId: string;
  live: boolean;
  /** Called after a speaker was named, so the minutes can pick up the new owners. */
  onSpeakerRenamed?: () => void;
}) {
  const [segments, setSegments] = useState<Segment[]>([]);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);
  // A speaker can be named once the call is over and the transcript is final.
  const canRename = REVIEW_AVAILABLE && !live;

  useEffect(() => {
    let cancelled = false;
    let loading = false;

    async function load() {
      if (loading) return;
      loading = true;
      try {
        const result = await getSegments(meetingId);
        if (cancelled) return;
        setSegments(result);
        setError(false);
      } catch {
        if (!cancelled) setError(true);
      } finally {
        loading = false;
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
  }, [meetingId, live, refresh]);

  // Named speakers alternate blue and orange by order of first appearance; unknown speakers stay neutral.
  const styles = useMemo(() => {
    const map = new Map<string, string>();
    for (const { speaker } of segments) {
      if (map.has(speaker)) continue;
      if (isUnnamedSpeaker(speaker)) {
        map.set(speaker, UNKNOWN_STYLE);
      } else {
        const named = [...map.values()].filter((v) => v !== UNKNOWN_STYLE).length;
        map.set(speaker, NAMED_STYLES[named % NAMED_STYLES.length]);
      }
    }
    return map;
  }, [segments]);

  function startNaming(speaker: string) {
    setEditing(speaker);
    setName("");
    setRenameError(null);
  }

  async function applyName(speaker: string, value: string) {
    const tidy = tidyName(value);
    if (!tidy) {
      setRenameError("Enter a name of up to 200 characters.");
      return;
    }
    setRenaming(true);
    setRenameError(null);
    try {
      await renameSpeaker(meetingId, speaker, tidy);
      setEditing(null);
      setRefresh((n) => n + 1);
      onSpeakerRenamed?.();
    } catch (cause) {
      setRenameError(
        cause instanceof ApiError && cause.status === 409
          ? "These minutes are validated and locked, so their speakers cannot change."
          : errorMessage(cause, "Could not save the name. Try again."),
      );
    } finally {
      setRenaming(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>, speaker: string) {
    event.preventDefault();
    if (!renaming) void applyName(speaker, name);
  }

  const unnamed = new Set(segments.map((s) => s.speaker).filter(isUnnamedSpeaker));

  return (
    <section
      aria-labelledby="transcript-title"
      className="card p-6 sm:p-8"
    >
      <h2 id="transcript-title" className="mb-5 flex items-center gap-2 font-display text-lg font-bold">
        Transcript
        {live && (
          <span className="chip bg-foreground text-white">
            live
          </span>
        )}
      </h2>
      {canRename && unnamed.size > 0 && (
        <p className="mb-4 rounded-xl border border-accent-line bg-accent-soft p-4 text-sm text-accent-ink">
          {unnamed.size === 1 ? "One speaker was" : `${unnamed.size} speakers were`} not named by
          the capture. If you know who it is, name them: the name is applied to every line and to
          the owners in the minutes.
        </p>
      )}
      {error && (
        <p role="alert" className="mb-3 text-sm text-red-700">
          {live ? "Cannot load the transcript. Retrying…" : "Cannot load the transcript."}{" "}
          <button type="button" onClick={() => setRefresh((value) => value + 1)} className="underline">Try again</button>
        </p>
      )}
      {segments.length === 0 ? (
        <p className="text-sm text-muted">
          {live ? "Waiting for the first segments…" : "No transcript available."}
        </p>
      ) : (
        <ol className="flex flex-col gap-4">
          {segments.map((segment, index) => (
            <li id={`segment-${index}`} key={segment.segment_id} className="flex scroll-mt-6 gap-3 target:rounded-xl target:bg-accent-soft">
              <span
                aria-hidden="true"
                className={`flex h-8 w-8 flex-none items-center justify-center rounded-full text-xs font-semibold ${styles.get(segment.speaker) ?? UNKNOWN_STYLE}`}
              >
                {initials(segment.speaker)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-x-2 text-sm">
                  <span className="font-medium">{segment.speaker}</span>
                  <span className="text-xs text-faint">{formatTime(segment.start)}</span>
                  {canRename && isUnnamedSpeaker(segment.speaker) && editing !== segment.speaker && (
                    <button
                      type="button"
                      onClick={() => startNaming(segment.speaker)}
                      aria-label={`Name ${segment.speaker}`}
                      className="min-h-8 text-xs font-semibold text-brand underline"
                    >
                      Name this speaker
                    </button>
                  )}
                </p>
                {editing === segment.speaker && (
                  <form
                    onSubmit={(event) => onSubmit(event, segment.speaker)}
                    className="my-2 flex flex-col gap-2 rounded-xl border border-line bg-background p-3"
                    aria-label={`Name ${segment.speaker}`}
                  >
                    <label className="flex flex-col gap-1 text-sm font-medium">
                      Who is {segment.speaker}?
                      <input
                        autoFocus
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        maxLength={200}
                        className="field min-h-10 text-sm font-normal"
                      />
                    </label>
                    {knownNames(segments, segment.speaker).length > 0 && (
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                        <span>Or one of them:</span>
                        {knownNames(segments, segment.speaker).map((known) => (
                          <button
                            key={known}
                            type="button"
                            disabled={renaming}
                            onClick={() => void applyName(segment.speaker, known)}
                            className="rounded-full border border-line px-3 py-1 font-medium text-foreground hover:bg-surface"
                          >
                            {known}
                          </button>
                        ))}
                      </div>
                    )}
                    {renameError && (
                      <p role="alert" className="text-sm text-red-700">
                        {renameError}
                      </p>
                    )}
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={renaming}
                        className="btn btn-primary min-h-10 px-4 text-sm"
                      >
                        {renaming ? "Saving…" : "Apply to all lines"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditing(null)}
                        disabled={renaming}
                        className="btn btn-secondary min-h-10 px-4 text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}
                <p className={segment.is_final ? "" : "text-muted"}>{segment.text}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
