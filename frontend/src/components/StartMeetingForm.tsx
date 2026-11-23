"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { getBotName, startCapture } from "@/lib/api/captures";
import { errorMessage } from "@/lib/api/client";
import { getTemplates, type MinutesTemplate } from "@/lib/api/templates";
import { isGoogleMeetUrl, normalizeGoogleMeetUrl } from "@/lib/meet";

export function StartMeetingForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [botName, setBotName] = useState<string | null>(null);
  const [templates, setTemplates] = useState<MinutesTemplate[]>([]);
  const [template, setTemplate] = useState("standard");

  useEffect(() => {
    getBotName().then(setBotName).catch(() => undefined);
    // If the list cannot be loaded the form still works with the standard template.
    getTemplates()
      .then((list) => {
        setTemplates(list);
        setTemplate(list.find((item) => item.default)?.id ?? "standard");
      })
      .catch(() => undefined);
  }, []);

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
        meeting_url: normalizeGoogleMeetUrl(url), title: title.trim(), template, participants_informed: true,
      });
      router.push(`/meetings/${encodeURIComponent(capture_id)}`);
    } catch (error) {
      setError(errorMessage(error, "Could not start the capture. Check that the API is reachable."));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="card flex flex-col gap-5 p-8" noValidate>
      <label className="flex flex-col gap-2 text-sm font-semibold">
        Meeting title
        <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200}
          required disabled={pending} placeholder="Weekly project sync"
          className="field" />
      </label>
      <div className="flex flex-col gap-2">
        <label htmlFor="meeting-url" className="text-sm font-semibold">
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
          className="field aria-invalid:border-red-500"
        />
        {error && (
          <p id="meeting-url-error" role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
      </div>
      <label className="flex flex-col gap-2 text-sm font-semibold">
        Minutes template
        <select value={template} onChange={(event) => setTemplate(event.target.value)}
          className="field" disabled={pending}>
          {templates.length === 0 && (
            <option value="standard">Standard: summary, decisions and actions</option>
          )}
          {templates.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name.en ?? item.id}: {item.description.en ?? ""}
            </option>
          ))}
        </select>
      </label>
      {botName && (
        <p className="text-sm leading-relaxed text-secondary">
          The assistant joins as a visible participant named <strong>{botName}</strong>. Tell the
          participants before you start: it cannot post a notice in the meeting chat.
        </p>
      )}
      <label className="flex items-start gap-3 rounded-xl border border-accent-line bg-accent-soft px-4 py-3 text-sm leading-normal text-accent-ink">
        <input type="checkbox" checked={consent} required disabled={pending}
          onChange={(event) => setConsent(event.target.checked)} className="mt-1 h-4 w-4 accent-[#2457f5]" />
        Participants have been informed and consent to transcription and AI draft generation.
      </label>
      <button
        type="submit"
        disabled={pending}
        className="btn btn-primary self-start"
      >
        {pending ? "Starting…" : "Start capture"}
      </button>
    </form>
  );
}
