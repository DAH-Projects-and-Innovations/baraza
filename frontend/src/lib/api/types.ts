/** API types. Keep in sync with the backend (backend/src/baraza). */

export interface Health {
  status: string;
  version: string;
  llm_is_external: boolean;
}

/** Mirrors `CaptureStatus` in backend/src/baraza/adapters/base.py. */
export type CaptureStatus =
  | "waiting_admission"
  | "capturing"
  | "processing"
  | "done"
  | "failed";

/** Mirrors `TranscriptSegment` in backend/src/baraza/core/segments.py. */
export interface Segment {
  meeting_id: string;
  segment_id: string;
  speaker: string;
  speaker_id: string | null;
  start: number;
  end: number;
  text: string;
  language: string | null;
  is_final: boolean;
}

/** `POST /captures`. Consent is checked again by the backend. */
export interface StartCaptureRequest {
  meeting_url: string;
  title: string;
  template: string;
  participants_informed: true;
}

export interface StartCaptureResponse {
  capture_id: string;
}

/** Proposed contract: `GET /captures/{id}` and `POST /captures/{id}/stop`. */
export interface CaptureStatusResponse {
  capture_id: string;
  status: CaptureStatus;
  meeting_id?: string;
  title?: string;
  simulated?: boolean;
  stop_requested?: boolean;
  phase?: string;
  error?: string | null;
  can_retry?: boolean;
}

/** Mirrors `Minutes` in backend/src/baraza/core/minutes.py. Missing info is `null`. */
export interface SourceRef {
  segment_indices: number[];
}

export interface Minutes {
  summary: string;
  topics: { title: string; summary: string; source: SourceRef }[];
  decisions: { text: string; source: SourceRef }[];
  actions: { text: string; owner: string | null; due_date: string | null; source: SourceRef }[];
  open_points: { text: string; source: SourceRef }[];
}

/** Review state of the minutes. Mirrors backend/src/baraza/core/minutes_review.py. */
export type MinutesStatus = "draft" | "validated";

export interface MinutesCounts {
  decisions: number;
  actions: number;
  actions_without_owner: number;
  actions_without_deadline: number;
  open_points: number;
}

/** `GET /meetings`. Mirrors `MeetingSummary` in backend/src/baraza/api/meetings.py. */
export interface MeetingSummary {
  meeting_id: string;
  title: string;
  status: CaptureStatus;
  started_at: string;
  simulated: boolean;
  duration_seconds: number | null;
  participants: number;
  minutes_status: MinutesStatus | null;
  minutes_version: number;
  needs_review: boolean;
  counts: MinutesCounts | null;
}

export interface MeetingList {
  items: MeetingSummary[];
  total: number;
  limit: number;
  offset: number;
}

/** A check the backend applied to the draft: something removed or cleared as unsupported. */
export interface Correction {
  kind: "item_rejected" | "owner_nulled" | "due_date_nulled" | "due_date_year_adjusted";
  item_type: "topic" | "decision" | "action" | "open_point";
  item_position: number;
  original_value: string | null;
  reason: string;
}

/** `GET /meetings/{id}/minutes/meta`. */
export interface MinutesState {
  meeting_id: string;
  status: MinutesStatus;
  version: number;
  validated_by: string | null;
  validated_at: string | null;
  prompt_version: string | null;
  corrections: Correction[];
  counts: MinutesCounts;
}

export interface RevisionSummary {
  version: number;
  saved_by: string;
  saved_at: string;
  status: MinutesStatus;
}
