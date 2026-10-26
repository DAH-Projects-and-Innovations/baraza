import { USE_MOCK_API } from "@/lib/config";
import { apiFetch } from "./client";
import type { StartCaptureRequest, StartCaptureResponse } from "./types";

export async function startCapture(meetingUrl: string): Promise<StartCaptureResponse> {
  if (USE_MOCK_API) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return { capture_id: `mock-${Date.now()}` };
  }
  const body: StartCaptureRequest = { meeting_url: meetingUrl };
  return apiFetch<StartCaptureResponse>("/captures", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
