"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { startCapture } from "@/lib/api/captures";
import { errorMessage } from "@/lib/api/client";
import { isGoogleMeetUrl, normalizeGoogleMeetUrl } from "@/lib/meet";

export function StartMeetingForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (!title.trim() || !consent) {
      setError("Enter a title and confirm that participants are informed and consent to capture.");
      return;
    }
    if (!isGoogleMeetUrl(url)) {
      setError("Enter a valid Google Meet link, e.g. https://meet.google.com/abc-defg-hij");
      return;
    }
    setError(null);
    setPending(true);
    try {
      const { capture_id } = await startCapture({
        meeting_url: normalizeGoogleMeetUrl(url), title: title.trim(), template: "standard", participants_informed: true,
      });
      router.push(`/meetings/${encodeURIComponent(capture_id)}`);
    } catch (error) {
      setError(errorMessage(error, "Could not start the capture. Check that the API is reachable."));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        Meeting title
        <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200}
          required disabled={pending} placeholder="Weekly project sync"
          className="rounded-lg border border-line bg-surface px-3 py-2.5" />
      </label>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="meeting-url" className="text-sm font-medium">
          Google Meet link
        </label>
        <input
          id="meeting-url"
          type="url"
          required
          disabled={pending}
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
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        Minutes template
        <select className="rounded-lg border border-line bg-surface px-3 py-2.5" disabled={pending}>
          <option value="standard">Standard: summary, decisions and actions</option>
        </select>
      </label>
      <label className="flex items-start gap-2 rounded-lg bg-accent-soft px-3 py-2.5 text-sm text-accent-ink">
        <input type="checkbox" checked={consent} required disabled={pending}
          onChange={(event) => setConsent(event.target.checked)} className="mt-1" />
        Participants have been informed and consent to transcription and AI draft generation.
      </label>
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
