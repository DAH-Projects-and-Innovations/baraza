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

/** Mirrors `Segment` in backend/src/baraza/core/transcript.py. */
export interface Segment {
  speaker: string;
  start: number;
  end: number;
  text: string;
}

/** Proposed contract, to confirm with the backend (#125/#126): `POST /captures`. */
export interface StartCaptureRequest {
  meeting_url: string;
}

export interface StartCaptureResponse {
  capture_id: string;
}
