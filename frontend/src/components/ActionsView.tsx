"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { errorMessage } from "@/lib/api/client";
import { getMinutes } from "@/lib/api/meetings";
import type { MeetingSummary, Minutes } from "@/lib/api/types";
import { useAuth } from "./AuthProvider";
import { LoadError, useMeetings } from "./MeetingList";

type Scope = "mine" | "everyone";
type Loaded = { meeting: MeetingSummary; actions: Minutes["actions"] };

/** Actions from validated minutes only: a draft is not a commitment yet. */
export function ActionsView() {
  const { user } = useAuth();
  const { meetings, error, retry } = useMeetings();
  const [groups, setGroups] = useState<Loaded[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [scope, setScope] = useState<Scope>("everyone");

  useEffect(() => {
    if (!meetings) return;
    let cancelled = false;
    const validated = meetings.filter((m) => m.minutes_status === "validated");
    Promise.all(
      validated.map(async (meeting) => ({
        meeting,
        actions: (await getMinutes(meeting.meeting_id))?.actions ?? [],
      })),
    )
      .then((result) => {
        if (!cancelled) setGroups(result.filter((g) => g.actions.length > 0));
      })
      .catch((cause) => {
        if (!cancelled) setProblem(errorMessage(cause, "Cannot load the actions."));
      });
    return () => {
      cancelled = true;
    };
  }, [meetings]);

  const shown = useMemo(() => {
    const me = user?.name.trim().toLowerCase() ?? "";
    const isMine = (owner: string | null) => !!owner && !!me && owner.trim().toLowerCase() === me;
    return (groups ?? [])
      .map((g) => ({ ...g, actions: scope === "mine" ? g.actions.filter((a) => isMine(a.owner)) : g.actions }))
      .filter((g) => g.actions.length > 0);
  }, [groups, scope, user]);
  const total = shown.reduce((sum, g) => sum + g.actions.length, 0);

  if (error) return <LoadError error={error} retry={retry} />;
  if (problem) return <LoadError error={problem} retry={() => window.location.reload()} />;
  if (meetings === null || groups === null) return <p className="text-sm text-muted">Loading the actions…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-[15px] text-muted">
          From validated meetings only. {total} {total === 1 ? "action" : "actions"}.
        </span>
        <div className="flex gap-2" role="group" aria-label="Whose actions">
          {(["mine", "everyone"] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={scope === value}
              onClick={() => setScope(value)}
              className={`rounded-full px-4 py-2 text-sm font-semibold ${
                scope === value ? "bg-foreground text-white" : "border border-[#d7dbe8] bg-surface text-secondary"
              }`}
            >
              {value === "mine" ? "Mine" : "Everyone"}
            </button>
          ))}
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="card flex flex-col items-start gap-3 p-8">
          <h2 className="font-display text-xl font-bold">No action to show yet</h2>
          <p className="max-w-lg text-[15px] leading-relaxed text-secondary">
            Actions appear here once the minutes of a meeting are validated.
            {scope === "mine" && " Only actions whose owner is your name are listed under Mine."}
          </p>
          <Link href="/meetings" className="btn btn-secondary">See the meetings</Link>
        </div>
      ) : (
        shown.map(({ meeting, actions }) => (
          <section key={meeting.meeting_id} className="flex flex-col gap-2.5">
            <h2 className="font-serif text-xl font-medium">
              <Link href={`/meetings/${encodeURIComponent(meeting.meeting_id)}`} className="hover:underline">
                {meeting.title}
              </Link>
            </h2>
            <ul className="card divide-y divide-line overflow-hidden rounded-[20px]">
              {actions.map((a, i) => (
                <li key={i} className="flex items-start gap-3.5 px-5 py-4">
                  <span aria-hidden="true" className="mt-0.5 h-5.5 w-5.5 flex-none rounded-[7px] border-[1.5px] border-faint" />
                  <span className="flex flex-col gap-2">
                    <span className="text-[15px] leading-snug">{a.text}</span>
                    <span className="flex flex-wrap gap-2">
                      {a.owner ? <span className="chip-validated">{a.owner}</span> : <span className="chip-missing">Owner not specified</span>}
                      {a.due_date ? <span className="chip-validated">{a.due_date}</span> : <span className="chip-missing">Deadline not specified</span>}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
