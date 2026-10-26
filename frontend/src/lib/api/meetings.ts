import { USE_MOCK_API } from "@/lib/config";
import { getCaptureStatus } from "./captures";
import { ApiError, apiFetch } from "./client";
import {
  MOCK_MINUTES,
  MOCK_SEGMENT_COUNT,
  MOCK_SEGMENT_INTERVAL_MS,
  mockSegments,
} from "./mock-data";
import type { Minutes, Segment } from "./types";

const MOCK_PREFIX = "mock-";
/** In the mock, the bot is admitted 5 s after the start (see captures.ts). */
const MOCK_ADMISSION_MS = 5000;

export async function getSegments(meetingId: string): Promise<Segment[]> {
  if (USE_MOCK_API) {
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
 * Proposed contract, to confirm with the AI pipeline (#89): `GET /meetings/{id}/minutes` returns
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
