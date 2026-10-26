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

/** Proposed contract, to confirm with the backend (#125/#126): `POST /captures`. */
export interface StartCaptureRequest {
  meeting_url: string;
}

export interface StartCaptureResponse {
  capture_id: string;
}

/** Proposed contract: `GET /captures/{id}` and `POST /captures/{id}/stop`. */
export interface CaptureStatusResponse {
  capture_id: string;
  status: CaptureStatus;
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
