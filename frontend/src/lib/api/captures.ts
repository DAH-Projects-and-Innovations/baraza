import { USE_MOCK_API } from "@/lib/config";
import { ApiError, apiFetch } from "./client";
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

export async function startCapture(body: StartCaptureRequest): Promise<StartCaptureResponse> {
  if (USE_MOCK_API) {
    await delay(500);
    const capture_id = `${MOCK_PREFIX}${Date.now()}`;
    sessionStorage.setItem(`baraza-mock-title-${capture_id}`, body.title);
    return { capture_id };
  }
  return apiFetch<StartCaptureResponse>("/captures", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getCaptureStatus(captureId: string): Promise<CaptureStatusResponse> {
  if (USE_MOCK_API) {
    if (!/^mock-\d+$/.test(captureId)) throw new ApiError(404, "Meeting not found");
    return {
      capture_id: captureId, meeting_id: captureId, status: mockStatus(captureId),
      title: sessionStorage.getItem(`baraza-mock-title-${captureId}`) ?? "Fictional meeting",
      simulated: true,
    };
  }
  return apiFetch<CaptureStatusResponse>(`/captures/${encodeURIComponent(captureId)}`, {
    cache: "no-store",
  });
}

export async function retryGeneration(meetingId: string): Promise<void> {
  await apiFetch(`/meetings/${encodeURIComponent(meetingId)}/retry`, { method: "POST" });
}

export async function stopCapture(captureId: string): Promise<CaptureStatusResponse | void> {
  if (USE_MOCK_API) {
    await delay(300);
    sessionStorage.setItem(mockStopKey(captureId), String(Date.now()));
    return;
  }
  return apiFetch<CaptureStatusResponse>(`/captures/${encodeURIComponent(captureId)}/stop`, { method: "POST" });
}
