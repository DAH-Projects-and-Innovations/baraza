import { USE_MOCK_API } from "@/lib/config";
import { getCaptureStatus } from "./captures";
import { ApiError, apiFetch } from "./client";
import {
  MOCK_MINUTES,
  MOCK_SEGMENT_COUNT,
  MOCK_SEGMENT_INTERVAL_MS,
  mockSegments,
} from "./mock-data";
import type { MeetingList, Minutes, MinutesState, RevisionSummary, Segment } from "./types";

const MOCK_PREFIX = "mock-";
/** In the mock, the bot is admitted 5 s after the start (see captures.ts). */
const MOCK_ADMISSION_MS = 5000;

export async function getSegments(meetingId: string): Promise<Segment[]> {
  if (USE_MOCK_API) {
    if ((await getCaptureStatus(meetingId)).status === "done") {
      return mockSegments(meetingId, MOCK_SEGMENT_COUNT);
    }
    const startedAt = Number(meetingId.slice(MOCK_PREFIX.length));
    if (Number.isNaN(startedAt)) return [];
    const elapsed = Date.now() - startedAt - MOCK_ADMISSION_MS;
    const revealed = Math.floor(elapsed / MOCK_SEGMENT_INTERVAL_MS) + 1;
    return mockSegments(meetingId, Math.max(0, Math.min(MOCK_SEGMENT_COUNT, revealed)));
  }
  return apiFetch<Segment[]>(`/meetings/${encodeURIComponent(meetingId)}/segments`, {
    cache: "no-store",
  });
}

/**
 * `GET /meetings/{id}/minutes` returns
 * the minutes, or 404 while they are not generated yet.
 */
export async function getMinutes(meetingId: string): Promise<Minutes | null> {
  if (USE_MOCK_API) {
    const { status } = await getCaptureStatus(meetingId);
    return status === "done" ? MOCK_MINUTES : null;
  }
  try {
    return await apiFetch<Minutes>(`/meetings/${encodeURIComponent(meetingId)}/minutes`, {
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** The minutes together with their review state. */
export interface MinutesDoc {
  minutes: Minutes;
  state: MinutesState;
}

/** Saving and validating need the real backend: the browser simulation is read-only. */
export const REVIEW_AVAILABLE = !USE_MOCK_API;

/** `null` while the minutes are not generated yet. */
export async function getMinutesDoc(meetingId: string): Promise<MinutesDoc | null> {
  if (USE_MOCK_API) {
    const minutes = await getMinutes(meetingId);
    if (!minutes) return null;
    return {
      minutes,
      state: {
        meeting_id: meetingId,
        status: "draft",
        version: 1,
        validated_by: null,
        validated_at: null,
        prompt_version: null,
        corrections: [],
        counts: {
          decisions: minutes.decisions.length,
          actions: minutes.actions.length,
          actions_without_owner: minutes.actions.filter((a) => !a.owner).length,
          actions_without_deadline: minutes.actions.filter((a) => !a.due_date).length,
          open_points: minutes.open_points.length,
        },
      },
    };
  }
  const id = encodeURIComponent(meetingId);
  try {
    const [minutes, state] = await Promise.all([
      apiFetch<Minutes>(`/meetings/${id}/minutes`, { cache: "no-store" }),
      apiFetch<MinutesState>(`/meetings/${id}/minutes/meta`, { cache: "no-store" }),
    ]);
    return { minutes, state };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** Save an edit. `version` is the one being edited: a stale one is refused with 412. */
export function saveMinutes(meetingId: string, minutes: Minutes, version: number) {
  return apiFetch<MinutesState>(`/meetings/${encodeURIComponent(meetingId)}/minutes`, {
    method: "PUT",
    headers: { "If-Match": `"${version}"` },
    body: JSON.stringify(minutes),
  });
}

/** Validate the draft. The minutes are locked afterwards (later saves get 409). */
export function validateMinutes(meetingId: string, version: number) {
  return apiFetch<MinutesState>(`/meetings/${encodeURIComponent(meetingId)}/minutes/validate`, {
    method: "POST",
    headers: { "If-Match": `"${version}"` },
  });
}

export function getRevisions(meetingId: string) {
  return apiFetch<RevisionSummary[]>(
    `/meetings/${encodeURIComponent(meetingId)}/minutes/revisions`,
    { cache: "no-store" },
  );
}

/** Meeting history, most recent first. Empty in the browser simulation. */
export async function listMeetings(
  options: { needsReview?: boolean; limit?: number } = {},
): Promise<MeetingList> {
  if (USE_MOCK_API) return { items: [], total: 0, limit: 50, offset: 0 };
  const query = new URLSearchParams();
  if (options.needsReview !== undefined) query.set("needs_review", String(options.needsReview));
  if (options.limit) query.set("limit", String(options.limit));
  const suffix = query.size > 0 ? `?${query}` : "";
  return apiFetch<MeetingList>(`/meetings${suffix}`, { cache: "no-store" });
}

export interface RenameResult {
  renamed_segments: number;
  /** Set when the draft's action owners changed too: the minutes have a new version. */
  minutes_version: number | null;
}

/** Give a name to a speaker the capture could not name. Not available in the simulation. */
export function renameSpeaker(meetingId: string, from: string, to: string) {
  return apiFetch<RenameResult>(`/meetings/${encodeURIComponent(meetingId)}/speakers/rename`, {
    method: "POST",
    body: JSON.stringify({ from_name: from, to_name: to }),
  });
}
