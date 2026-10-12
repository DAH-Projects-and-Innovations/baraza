"use client";

import { useState, type FormEvent } from "react";
import { startCapture } from "@/lib/api/captures";
import { isGoogleMeetUrl } from "@/lib/meet";

export function StartMeetingForm() {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [captureId, setCaptureId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCaptureId(null);
    if (!isGoogleMeetUrl(url)) {
      setError("Enter a valid Google Meet link, e.g. https://meet.google.com/abc-defg-hij");
      return;
    }
    setError(null);
    setPending(true);
    try {
      const { capture_id } = await startCapture(url.trim());
      setCaptureId(capture_id);
    } catch {
      setError("Could not start the capture. Check that the API is reachable.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
      <label htmlFor="meeting-url" className="text-sm font-medium">
        Google Meet link
      </label>
      <input
        id="meeting-url"
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://meet.google.com/abc-defg-hij"
        aria-invalid={error !== null}
        aria-describedby={error ? "meeting-url-error" : undefined}
        className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
      />
      {error && (
        <p id="meeting-url-error" role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {pending ? "Starting…" : "Start capture"}
      </button>
      {captureId && (
        <p role="status" className="text-sm text-zinc-600 dark:text-zinc-400">
          Capture started (<code>{captureId}</code>). Live status comes with #160.
        </p>
      )}
      <p className="text-xs text-zinc-500">
        Inform participants and get their consent before capturing a meeting. The bot joins as a
        visible participant.
      </p>
    </form>
  );
}
