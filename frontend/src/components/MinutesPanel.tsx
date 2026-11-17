"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ApiError, errorMessage } from "@/lib/api/client";
import {
  REVIEW_AVAILABLE,
  getMinutesDoc,
  getRevisions,
  saveMinutes,
  validateMinutes,
  type MinutesDoc,
} from "@/lib/api/meetings";
import type { Correction, Minutes, RevisionSummary, SourceRef } from "@/lib/api/types";
import { actorLabel, countGaps, removeAt, replaceAt, sameMinutes, toOptional } from "@/lib/minutes";

const NOT_SPECIFIED = "Not specified";
const POLL_INTERVAL_MS = 3000;

const INPUT =
  "w-full rounded-lg border border-line bg-background px-3 py-2 text-sm text-foreground";
const INPUT_EMPTY = "border-dashed border-accent";
const BUTTON = "rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60";

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MinutesPanel({ meetingId, ready }: { meetingId: string; ready: boolean }) {
  const [doc, setDoc] = useState<MinutesDoc | null>(null);
  const [draft, setDraft] = useState<Minutes | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [notice, setNotice] = useState<{ message: string; reload: boolean } | null>(null);
  const [busy, setBusy] = useState<"save" | "validate" | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [revisions, setRevisions] = useState<RevisionSummary[]>([]);
  const loaded = doc !== null;

  useEffect(() => {
    if (!ready || loaded) return;
    let cancelled = false;
    let loading = false;

    async function load() {
      if (loading) return;
      loading = true;
      try {
        const result = await getMinutesDoc(meetingId);
        if (cancelled) return;
        if (result) {
          setDoc(result);
          setDraft(result.minutes);
        }
        setLoadError(false);
      } catch {
        if (!cancelled) setLoadError(true);
      } finally {
        loading = false;
      }
    }

    // Minutes can take a while to generate: poll until they exist.
    void load();
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [meetingId, ready, loaded]);

  const version = doc?.state.version;
  useEffect(() => {
    if (!REVIEW_AVAILABLE || version === undefined) return;
    let cancelled = false;
    getRevisions(meetingId)
      .then((result) => {
        if (!cancelled) setRevisions(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [meetingId, version]);

  const reload = useCallback(async () => {
    try {
      const result = await getMinutesDoc(meetingId);
      if (result) {
        setDoc(result);
        setDraft(result.minutes);
      }
      setNotice(null);
      setConfirming(false);
      setConfirmed(false);
    } catch (error) {
      setNotice({ message: errorMessage(error, "Cannot reload the minutes."), reload: false });
    }
  }, [meetingId]);

  function explain(error: unknown, fallback: string) {
    if (error instanceof ApiError && error.status === 412) {
      return {
        message:
          "Someone saved a newer version while you were editing. Reload to see it. Your unsaved changes will be lost.",
        reload: true,
      };
    }
    if (error instanceof ApiError && error.status === 409) {
      return { message: "These minutes were validated and are now locked.", reload: true };
    }
    return { message: errorMessage(error, fallback), reload: false };
  }

  async function onSave() {
    if (!doc || !draft || busy) return;
    setBusy("save");
    try {
      const state = await saveMinutes(meetingId, draft, doc.state.version);
      setDoc({ minutes: draft, state });
      setNotice(null);
    } catch (error) {
      setNotice(explain(error, "Could not save. Your changes are still here: try again."));
    } finally {
      setBusy(null);
    }
  }

  async function onValidate() {
    if (!doc || busy) return;
    setBusy("validate");
    try {
      const state = await validateMinutes(meetingId, doc.state.version);
      setDoc({ minutes: doc.minutes, state });
      setConfirming(false);
      setConfirmed(false);
      setNotice(null);
    } catch (error) {
      setNotice(explain(error, "Could not validate. Try again."));
    } finally {
      setBusy(null);
    }
  }

  if (!ready) return null;

  const state = doc?.state;
  const validated = state?.status === "validated";
  const editable = REVIEW_AVAILABLE && !!state && !validated;
  const dirty = !!doc && !!draft && !sameMinutes(draft, doc.minutes);
  const shown = draft ?? doc?.minutes ?? null;
  const gaps = doc ? countGaps(doc.minutes) : { ownerMissing: 0, dueMissing: 0 };

  function patch(change: (minutes: Minutes) => Minutes) {
    setDraft((current) => (current ? change(current) : current));
  }

  return (
    <section aria-labelledby="minutes-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="minutes-title" className="text-lg font-semibold tracking-tight">
          Minutes
        </h2>
        {validated && state ? (
          <span className="rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-brand-ink">
            Validated by {actorLabel(state.validated_by ?? "")}
            {state.validated_at && ` · ${formatDateTime(state.validated_at)}`}
          </span>
        ) : (
          <span className="rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-ink">
            AI draft, to review
          </span>
        )}
      </div>

      {loadError && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          Cannot load the minutes. Retrying…
        </p>
      )}
      {notice && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          <span>{notice.message}</span>
          {notice.reload && (
            <button type="button" onClick={() => void reload()} className="font-medium underline">
              Reload the latest version
            </button>
          )}
        </div>
      )}

      {!shown || !state ? (
        <p className="rounded-xl border border-line bg-surface p-4 text-sm text-muted">
          Generating the minutes…
        </p>
      ) : (
        <>
          {validated && (
            <p className="rounded-xl border border-line bg-brand-soft p-3 text-sm text-brand-ink">
              These minutes are validated and locked. Nothing is shared until you choose.
            </p>
          )}
          {!REVIEW_AVAILABLE && (
            <p className="rounded-xl border border-line bg-surface p-3 text-sm text-muted">
              Editing and validating need the real backend. This is the browser simulation.
            </p>
          )}
          {state.corrections.length > 0 && <CorrectionsNote corrections={state.corrections} />}

          <Card title="Summary">
            {editable ? (
              <textarea
                aria-label="Summary"
                rows={3}
                className={INPUT}
                value={shown.summary}
                onChange={(event) => patch((m) => ({ ...m, summary: event.target.value }))}
              />
            ) : (
              <p>{shown.summary}</p>
            )}
          </Card>

          {shown.topics.length > 0 && (
            <Card title="Topics">
              <ul className="flex flex-col gap-2">
                {shown.topics.map((t, i) => (
                  <li key={i}>
                    <span className="font-medium">{t.title}</span>
                    <span className="text-muted"> — {t.summary}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Card title="Decisions" tone="brand">
              {shown.decisions.length === 0 ? (
                <Missing />
              ) : (
                <ul className="flex flex-col gap-3">
                  {shown.decisions.map((d, i) => (
                    <li key={i} className="flex flex-col gap-1">
                      {editable ? (
                        <div className="flex gap-2">
                          <input
                            aria-label={`Decision ${i + 1}`}
                            className={INPUT}
                            value={d.text}
                            onChange={(event) =>
                              patch((m) => ({
                                ...m,
                                decisions: replaceAt(m.decisions, i, { ...d, text: event.target.value }),
                              }))
                            }
                          />
                          <RemoveButton
                            label={`Remove decision ${i + 1}`}
                            onClick={() => patch((m) => ({ ...m, decisions: removeAt(m.decisions, i) }))}
                          />
                        </div>
                      ) : (
                        <span>{d.text}</span>
                      )}
                      <Sources source={d.source} />
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card title="Actions" tone="accent">
              {shown.actions.length === 0 ? (
                <Missing />
              ) : (
                <ul className="flex flex-col gap-4">
                  {shown.actions.map((a, i) => (
                    <li key={i} className="flex flex-col gap-2">
                      {editable ? (
                        <>
                          <div className="flex gap-2">
                            <input
                              aria-label={`Action ${i + 1}`}
                              className={INPUT}
                              value={a.text}
                              onChange={(event) =>
                                patch((m) => ({
                                  ...m,
                                  actions: replaceAt(m.actions, i, { ...a, text: event.target.value }),
                                }))
                              }
                            />
                            <RemoveButton
                              label={`Remove action ${i + 1}`}
                              onClick={() => patch((m) => ({ ...m, actions: removeAt(m.actions, i) }))}
                            />
                          </div>
                          <div className="grid gap-2 sm:grid-cols-2">
                            <input
                              aria-label={`Owner of action ${i + 1}`}
                              placeholder="Owner not specified"
                              className={`${INPUT} ${a.owner ? "" : INPUT_EMPTY}`}
                              value={a.owner ?? ""}
                              onChange={(event) =>
                                patch((m) => ({
                                  ...m,
                                  actions: replaceAt(m.actions, i, { ...a, owner: toOptional(event.target.value) }),
                                }))
                              }
                            />
                            <input
                              aria-label={`Deadline of action ${i + 1}`}
                              placeholder="Deadline not specified"
                              className={`${INPUT} ${a.due_date ? "" : INPUT_EMPTY}`}
                              value={a.due_date ?? ""}
                              onChange={(event) =>
                                patch((m) => ({
                                  ...m,
                                  actions: replaceAt(m.actions, i, { ...a, due_date: toOptional(event.target.value) }),
                                }))
                              }
                            />
                          </div>
                        </>
                      ) : (
                        <>
                          <p>{a.text}</p>
                          <p className="text-xs text-muted">
                            <Field label="Owner" value={a.owner} /> · <Field label="Due" value={a.due_date} />
                          </p>
                        </>
                      )}
                      <Sources source={a.source} />
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card title="Open points">
            {shown.open_points.length === 0 ? (
              <Missing />
            ) : (
              <ul className="flex flex-col gap-3">
                {shown.open_points.map((p, i) => (
                  <li key={i} className="flex flex-col gap-1">
                    {editable ? (
                      <div className="flex gap-2">
                        <input
                          aria-label={`Open point ${i + 1}`}
                          className={INPUT}
                          value={p.text}
                          onChange={(event) =>
                            patch((m) => ({
                              ...m,
                              open_points: replaceAt(m.open_points, i, { ...p, text: event.target.value }),
                            }))
                          }
                        />
                        <RemoveButton
                          label={`Remove open point ${i + 1}`}
                          onClick={() => patch((m) => ({ ...m, open_points: removeAt(m.open_points, i) }))}
                        />
                      </div>
                    ) : (
                      <span>{p.text}</span>
                    )}
                    <Sources source={p.source} />
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {editable && (
            <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4">
              {confirming ? (
                <div className="flex flex-col gap-3" role="group" aria-label="Confirm the validation">
                  <h3 className="text-base font-semibold">Validate these minutes?</h3>
                  <ul className="text-sm text-muted">
                    <li>{doc!.minutes.decisions.length} decisions · {doc!.minutes.actions.length} actions</li>
                    {gaps.ownerMissing > 0 && (
                      <li>{gaps.ownerMissing} without an owner: they stay “{NOT_SPECIFIED}”.</li>
                    )}
                    {gaps.dueMissing > 0 && (
                      <li>{gaps.dueMissing} without a deadline: they stay “{NOT_SPECIFIED}”.</li>
                    )}
                  </ul>
                  <p className="text-sm text-muted">
                    Validated minutes are locked and recorded under your name. Nothing is shared
                    until you choose.
                  </p>
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={confirmed}
                      onChange={(event) => setConfirmed(event.target.checked)}
                      className="mt-1"
                    />
                    I read the minutes and checked the decisions against the transcript.
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void onValidate()}
                      disabled={!confirmed || busy !== null}
                      className={`${BUTTON} bg-foreground text-background`}
                    >
                      {busy === "validate" ? "Validating…" : "Validate the minutes"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirming(false)}
                      disabled={busy !== null}
                      className={`${BUTTON} border border-line`}
                    >
                      Keep editing
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void onSave()}
                    disabled={!dirty || busy !== null}
                    className={`${BUTTON} bg-brand text-white hover:bg-brand-strong`}
                  >
                    {busy === "save" ? "Saving…" : "Save changes"}
                  </button>
                  <button
                    type="button"
                    onClick={() => doc && setDraft(doc.minutes)}
                    disabled={!dirty || busy !== null}
                    className={`${BUTTON} border border-line`}
                  >
                    Discard changes
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirming(true)}
                    disabled={dirty || busy !== null}
                    className={`${BUTTON} border border-foreground sm:ml-auto`}
                  >
                    Validate…
                  </button>
                  {dirty && <p className="w-full text-xs text-muted">Save your changes before validating.</p>}
                </div>
              )}
            </div>
          )}

          {revisions.length > 0 && (
            <details className="rounded-xl border border-line bg-surface p-4 text-sm">
              <summary className="cursor-pointer font-medium">History ({revisions.length})</summary>
              <ol className="mt-3 flex flex-col gap-2 text-muted">
                {[...revisions].reverse().map((r) => (
                  <li key={r.version}>
                    Version {r.version} · {actorLabel(r.saved_by)} · {formatDateTime(r.saved_at)}
                    {r.status === "validated" && " · validated"}
                  </li>
                ))}
              </ol>
              <p className="mt-3 text-xs text-faint">Version 1 is always the assistant&apos;s original.</p>
            </details>
          )}
        </>
      )}
    </section>
  );
}

const CORRECTION_LABEL: Record<Correction["kind"], string> = {
  item_rejected: "Removed",
  owner_nulled: "Owner cleared",
  due_date_nulled: "Deadline cleared",
  due_date_year_adjusted: "Year corrected",
};

/** What the backend refused to present as a fact, so the reviewer knows it was left out. */
function CorrectionsNote({ corrections }: { corrections: Correction[] }) {
  return (
    <details className="rounded-xl border border-line bg-surface p-4 text-sm">
      <summary className="cursor-pointer font-medium">
        Checks applied to this draft ({corrections.length})
      </summary>
      <p className="mt-2 text-muted">
        The assistant removed or cleared what the transcript does not support.
      </p>
      <ul className="mt-2 flex flex-col gap-1 text-muted">
        {corrections.map((c, i) => (
          <li key={i}>
            <span className="font-medium text-foreground">{CORRECTION_LABEL[c.kind]}</span>
            {c.original_value && <> “{c.original_value}”</>} — {c.reason}
          </li>
        ))}
      </ul>
    </details>
  );
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="flex h-10 w-10 flex-none items-center justify-center rounded-lg border border-line text-muted hover:text-foreground"
    >
      <span aria-hidden="true">×</span>
    </button>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return value ? (
    <span>
      {label}: <span className="text-foreground">{value}</span>
    </span>
  ) : (
    <span className="italic text-faint">
      {label}: {NOT_SPECIFIED.toLowerCase()}
    </span>
  );
}

function Sources({ source }: { source: SourceRef }) {
  return (
    <span className="text-xs text-brand">
      {[...new Set(source.segment_indices)].map((index) => (
        <a
          key={index}
          href={`#segment-${index}`}
          className="mr-1 underline"
          aria-label={`Read transcript segment ${index + 1}`}
        >
          [{index + 1}]
        </a>
      ))}
    </span>
  );
}

function Missing() {
  return <p className="italic text-faint">{NOT_SPECIFIED}</p>;
}

function Card({
  title,
  tone,
  children,
}: {
  title: string;
  tone?: "brand" | "accent";
  children: ReactNode;
}) {
  const titleColor =
    tone === "brand" ? "text-brand-ink" : tone === "accent" ? "text-accent-ink" : "text-muted";
  return (
    <div className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <h3 className={`mb-2 text-xs font-semibold uppercase tracking-wide ${titleColor}`}>{title}</h3>
      {children}
    </div>
  );
}
