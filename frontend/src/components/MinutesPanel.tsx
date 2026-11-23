"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
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
import { exportFileName, minutesToMarkdown } from "@/lib/export";
import { actorLabel, countGaps, removeAt, replaceAt, sameMinutes, toOptional } from "@/lib/minutes";

const NOT_SPECIFIED = "Not specified";
const POLL_INTERVAL_MS = 3000;

const INPUT = "field min-h-11 text-[15px]";
const INPUT_EMPTY = "border-dashed border-accent";

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MinutesPanel({
  meetingId,
  ready,
  title,
  meta,
  reloadKey = 0,
}: {
  meetingId: string;
  ready: boolean;
  /** Shown as the heading of the minutes. */
  title: string;
  /** One line under the heading: date, duration, people. */
  meta: string;
  /** Changes when something outside the panel changed the minutes (a speaker was named). */
  reloadKey?: number;
}) {
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

  // Something outside changed the minutes: reload them, unless that would drop unsaved edits.
  const seenReload = useRef(reloadKey);
  useEffect(() => {
    if (reloadKey === seenReload.current || !doc) return;
    seenReload.current = reloadKey;
    const unsaved = draft !== null && !sameMinutes(draft, doc.minutes);
    void (async () => {
      if (!unsaved) return reload();
      setNotice({
        message:
          "A speaker was named, which updates the owners. Reload to see it: your unsaved changes will be lost.",
        reload: true,
      });
    })();
  }, [reloadKey, doc, draft, reload]);

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

  const dot = (tone: "accent" | "brand") => (
    <span aria-hidden="true" className={`mt-1.5 h-2.5 w-2.5 flex-none rounded-full ${tone === "accent" ? "bg-accent" : "bg-brand"}`} />
  );

  return (
    <section aria-labelledby="minutes-title" className="flex flex-col gap-4">
      <h2 id="minutes-title" className="sr-only">Minutes</h2>

      {loadError && (
        <p role="alert" className="text-sm text-red-700">Cannot load the minutes. Retrying…</p>
      )}
      {notice && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-800">
          <span>{notice.message}</span>
          {notice.reload && (
            <button type="button" onClick={() => void reload()} className="font-semibold underline">
              Reload the latest version
            </button>
          )}
        </div>
      )}

      {!shown || !state ? (
        <p className="card p-6 text-[15px] text-muted">Generating the minutes…</p>
      ) : (
        <div className="flex flex-wrap items-start gap-8">
          <article className="card flex min-w-0 flex-[3_1_480px] flex-col gap-8 p-6 shadow-[0_1px_2px_rgba(14,20,36,0.04)] sm:rounded-[28px] sm:p-12">
            <header className="flex flex-col gap-2.5">
              <span className="text-sm text-muted">{meta}</span>
              <h3 className="font-serif text-[40px] leading-[1.1] font-medium tracking-[-0.015em] sm:text-5xl">{title}</h3>
              <span className="flex flex-wrap gap-2">
                {validated ? (
                  <span className="chip-validated">
                    Validated by {actorLabel(state.validated_by ?? "")}
                    {state.validated_at && ` · ${formatDateTime(state.validated_at)}`}
                  </span>
                ) : (
                  <span className="chip-draft gap-2">
                    <span className="h-1.75 w-1.75 rounded-full bg-accent" />
                    Draft written by the assistant · not yet validated
                  </span>
                )}
              </span>
              {editable ? (
                <textarea
                  aria-label="Summary"
                  rows={3}
                  className={`${INPUT} font-serif text-xl leading-relaxed`}
                  value={shown.summary}
                  onChange={(event) => patch((m) => ({ ...m, summary: event.target.value }))}
                />
              ) : (
                <p className="font-serif text-[21px] leading-relaxed text-secondary">{shown.summary}</p>
              )}
            </header>

            {state.corrections.length > 0 && <CorrectionsNote corrections={state.corrections} />}
            {!REVIEW_AVAILABLE && (
              <p className="rounded-xl bg-background p-3 text-sm text-muted">
                Editing and validating need the real backend. This is the browser simulation.
              </p>
            )}

            {shown.topics.length > 0 && (
              <Block title="Topics">
                <ul className="flex flex-col gap-3">
                  {shown.topics.map((t, i) => (
                    <li key={i} className="font-serif text-xl leading-snug">
                      <span className="font-semibold">{t.title}</span>
                      <span className="text-secondary"> — {t.summary}</span>
                    </li>
                  ))}
                </ul>
              </Block>
            )}

            <Block title="Decisions">
              {shown.decisions.length === 0 ? (
                <Missing />
              ) : (
                <ul className="flex flex-col gap-3.5">
                  {shown.decisions.map((d, i) => (
                    <li key={i} className="flex flex-col gap-1.5 border-b border-line pb-3.5 last:border-b-0 last:pb-0">
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
                        <span className="font-serif text-[22px] leading-snug">{d.text}</span>
                      )}
                      <Sources source={d.source} />
                    </li>
                  ))}
                </ul>
              )}
            </Block>

            <Block title="Actions">
              {shown.actions.length === 0 ? (
                <Missing />
              ) : (
                <ul className="flex flex-col gap-5">
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
                        <div className="flex items-start gap-3.5">
                          <span aria-hidden="true" className="mt-1.5 h-5.5 w-5.5 flex-none rounded-[7px] border-[1.5px] border-faint" />
                          <div className="flex flex-col gap-2">
                            <p className="font-serif text-[21px] leading-snug">{a.text}</p>
                            <span className="flex flex-wrap gap-2">
                              <Pill value={a.owner} missing="Owner not specified" />
                              <Pill value={a.due_date} missing="Deadline not specified" />
                            </span>
                          </div>
                        </div>
                      )}
                      <Sources source={a.source} />
                    </li>
                  ))}
                </ul>
              )}
            </Block>

            <Block title="Open points">
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
                        <span className="font-serif text-[21px] leading-snug">{p.text}</span>
                      )}
                      <Sources source={p.source} />
                    </li>
                  ))}
                </ul>
              )}
            </Block>
          </article>

          <aside className="flex min-w-65 max-w-full flex-[1_1_280px] flex-col gap-4 lg:max-w-90">
            {validated ? (
              <div className="card flex flex-col gap-3 bg-brand-soft p-6">
                <span className="font-display text-lg font-bold text-brand-ink">Validated and locked</span>
                <span className="text-sm leading-normal text-secondary">
                  These minutes are recorded under a person&apos;s name. Nothing is shared until you choose.
                </span>
              </div>
            ) : editable ? (
              <div className="card flex flex-col gap-3.5 border-accent-line p-6 shadow-[0_8px_24px_rgba(255,122,47,0.1)]">
                {confirming ? (
                  <div className="flex flex-col gap-3.5" role="group" aria-label="Confirm the validation">
                    <h3 className="font-display text-lg font-bold">Validate these minutes?</h3>
                    <ul className="flex flex-col gap-1 text-sm text-secondary">
                      <li>{doc!.minutes.decisions.length} decisions · {doc!.minutes.actions.length} actions</li>
                      {gaps.ownerMissing > 0 && <li>{gaps.ownerMissing} without an owner: they stay “{NOT_SPECIFIED}”.</li>}
                      {gaps.dueMissing > 0 && <li>{gaps.dueMissing} without a deadline: they stay “{NOT_SPECIFIED}”.</li>}
                    </ul>
                    <p className="text-sm leading-normal text-muted">
                      Validated minutes are locked and recorded under your name. Nothing is shared until you choose.
                    </p>
                    <label className="flex items-start gap-3 text-sm leading-normal text-secondary">
                      <input
                        type="checkbox"
                        checked={confirmed}
                        onChange={(event) => setConfirmed(event.target.checked)}
                        className="mt-0.5 h-4.5 w-4.5 accent-[#2457f5]"
                      />
                      I read the minutes and checked the decisions against the transcript.
                    </label>
                    <button type="button" onClick={() => void onValidate()} disabled={!confirmed || busy !== null} className="btn btn-dark min-h-13">
                      {busy === "validate" ? "Validating…" : "Validate the minutes"}
                    </button>
                    <button type="button" onClick={() => setConfirming(false)} disabled={busy !== null} className="btn btn-secondary">
                      Keep editing
                    </button>
                  </div>
                ) : (
                  <>
                    <span className="font-display text-lg font-bold">Before you validate</span>
                    {gaps.dueMissing > 0 && (
                      <div className="flex items-start gap-3 text-sm leading-normal text-secondary">{dot("accent")}{gaps.dueMissing} {gaps.dueMissing === 1 ? "action has" : "actions have"} no deadline</div>
                    )}
                    {gaps.ownerMissing > 0 && (
                      <div className="flex items-start gap-3 text-sm leading-normal text-secondary">{dot("accent")}{gaps.ownerMissing} {gaps.ownerMissing === 1 ? "action has" : "actions have"} no owner</div>
                    )}
                    <div className="flex items-start gap-3 text-sm leading-normal text-secondary">{dot("brand")}Every item links to the transcript</div>
                    {dirty && <p className="text-xs text-muted">Save your changes before validating.</p>}
                    <button type="button" onClick={() => void onSave()} disabled={!dirty || busy !== null} className="btn btn-primary">
                      {busy === "save" ? "Saving…" : "Save changes"}
                    </button>
                    {dirty && (
                      <button type="button" onClick={() => doc && setDraft(doc.minutes)} disabled={busy !== null} className="btn btn-secondary">
                        Discard changes
                      </button>
                    )}
                    <button type="button" onClick={() => setConfirming(true)} disabled={dirty || busy !== null} className="btn btn-dark min-h-13">
                      Validate the minutes
                    </button>
                    <span className="text-center text-[13px] leading-normal text-muted">
                      Not specified stays not specified. You can validate with open items.
                    </span>
                  </>
                )}
              </div>
            ) : null}

            <ExportCard title={title} minutes={doc!.minutes} validated={validated} />

            <div className="card flex flex-col gap-2.5 p-6">
              <span className="font-display text-lg font-bold">Source</span>
              <span className="text-sm leading-normal text-secondary">
                Transcribed by the assistant from Google Meet.
              </span>
              <a href="#transcript-title" className="text-sm font-semibold text-brand">Read the full transcript</a>
            </div>

            {revisions.length > 0 && (
              <details className="card p-6 text-sm">
                <summary className="cursor-pointer font-display text-lg font-bold">History ({revisions.length})</summary>
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
          </aside>
        </div>
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
    <details className="rounded-2xl border border-line bg-background p-4 text-sm">
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
      className="flex h-11 w-11 flex-none items-center justify-center rounded-xl border border-line-strong bg-surface text-muted hover:text-foreground"
    >
      <span aria-hidden="true">×</span>
    </button>
  );
}

function Pill({ value, missing }: { value: string | null; missing: string }) {
  return value ? <span className="chip-validated">{value}</span> : <span className="chip-missing">{missing}</span>;
}

function Sources({ source }: { source: SourceRef }) {
  return (
    <span className="text-[13px] font-semibold text-brand">
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
  return <span className="chip-missing self-start">{NOT_SPECIFIED}</span>;
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h3 className="eyebrow">{title}</h3>
      {children}
    </section>
  );
}

function ExportCard({ title, minutes, validated }: { title: string; minutes: Minutes; validated: boolean }) {
  const [copied, setCopied] = useState(false);
  const markdown = () => minutesToMarkdown(title, minutes);

  function download() {
    const url = URL.createObjectURL(new Blob([markdown()], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = exportFileName(title);
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(markdown());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="card flex flex-col gap-3 p-6">
      <span className="font-display text-lg font-bold">Share and export</span>
      {validated ? (
        <>
          <span className="text-sm leading-normal text-secondary">Take the validated minutes with you.</span>
          <button type="button" onClick={download} className="btn btn-secondary">Download as Markdown</button>
          <button type="button" onClick={() => void copy()} className="btn btn-secondary">
            {copied ? "Copied" : "Copy as text"}
          </button>
        </>
      ) : (
        <span className="text-sm leading-normal text-secondary">
          Available after validation. A draft cannot be shared or exported.
        </span>
      )}
    </div>
  );
}
