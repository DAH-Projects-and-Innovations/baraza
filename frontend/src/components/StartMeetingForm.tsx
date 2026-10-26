"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { startCapture } from "@/lib/api/captures";
import { isGoogleMeetUrl } from "@/lib/meet";

export function StartMeetingForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isGoogleMeetUrl(url)) {
      setError("Enter a valid Google Meet link, e.g. https://meet.google.com/abc-defg-hij");
      return;
    }
    setError(null);
    setPending(true);
    try {
      const { capture_id } = await startCapture(url.trim());
      router.push(`/meetings/${encodeURIComponent(capture_id)}`);
    } catch {
      setError("Could not start the capture. Check that the API is reachable.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1.5">
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
          className="rounded-lg border border-line bg-surface px-3 py-2.5 aria-invalid:border-red-500"
        />
        {error && (
          <p id="meeting-url-error" role="alert" className="text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}
      </div>
      <p className="flex gap-2 rounded-lg bg-accent-soft px-3 py-2.5 text-sm text-accent-ink">
        <span aria-hidden="true">ⓘ</span>
        Tell participants and get their consent before capturing a meeting.
      </p>
      <button
        type="submit"
        disabled={pending}
        className="self-start rounded-lg bg-brand px-5 py-2.5 text-sm font-medium text-white hover:bg-brand-strong disabled:opacity-60"
      >
        {pending ? "Starting…" : "Start capture"}
      </button>
    </form>
  );
}
