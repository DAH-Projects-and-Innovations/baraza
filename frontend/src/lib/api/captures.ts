import { USE_MOCK_API } from "@/lib/config";
import { apiFetch } from "./client";
import type {
  CaptureStatus,
  CaptureStatusResponse,
  StartCaptureRequest,
  StartCaptureResponse,
} from "./types";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// --- Simulated backend (NEXT_PUBLIC_USE_MOCK_API) -------------------------------------------
// Status is derived from the time elapsed since the mock id was issued.
const MOCK_PREFIX = "mock-";

function mockStopKey(id: string) {
  return `baraza-mock-stopped-${id}`;
}

function mockStopTime(id: string): number | null {
  try {
    const value = sessionStorage.getItem(mockStopKey(id));
    return value ? Number(value) : null;
  } catch {
    return null;
  }
}

function mockStatus(id: string): CaptureStatus {
  const now = Date.now();
  const stoppedAt = mockStopTime(id);
  if (stoppedAt !== null) return now - stoppedAt < 4000 ? "processing" : "done";
  const startedAt = Number(id.slice(MOCK_PREFIX.length));
  if (Number.isNaN(startedAt)) return "failed";
  return now - startedAt < 5000 ? "waiting_admission" : "capturing";
}
// -------------------------------------------------------------------------------------------

export async function startCapture(meetingUrl: string): Promise<StartCaptureResponse> {
  if (USE_MOCK_API) {
    await delay(500);
    return { capture_id: `${MOCK_PREFIX}${Date.now()}` };
  }
  const body: StartCaptureRequest = { meeting_url: meetingUrl };
  return apiFetch<StartCaptureResponse>("/captures", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getCaptureStatus(captureId: string): Promise<CaptureStatusResponse> {
  if (USE_MOCK_API) {
    return { capture_id: captureId, status: mockStatus(captureId) };
  }
  return apiFetch<CaptureStatusResponse>(`/captures/${encodeURIComponent(captureId)}`, {
    cache: "no-store",
  });
}

export async function stopCapture(captureId: string): Promise<void> {
  if (USE_MOCK_API) {
    await delay(300);
    try {
      sessionStorage.setItem(mockStopKey(captureId), String(Date.now()));
    } catch {
      // sessionStorage unavailable: the mock simply keeps running.
    }
    return;
  }
  await apiFetch<unknown>(`/captures/${encodeURIComponent(captureId)}/stop`, { method: "POST" });
}
