import { API_URL } from "@/lib/config";
import type { Health } from "./types";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    /** Seconds to wait, when the API asked us to (429). */
    public readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Fired when the API says the session is over, so the app can send the person to sign in. */
export const SIGNED_OUT_EVENT = "baraza:signed-out";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    signal: AbortSignal.timeout(15000),
    // The session lives in an HttpOnly cookie that the browser sends on its own.
    credentials: "include",
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = typeof body?.detail === "string" ? body.detail : `${response.status} ${response.statusText}`;
    const retry = Number(response.headers.get("Retry-After"));
    if (response.status === 401 && path !== "/auth/login" && typeof window !== "undefined") {
      window.dispatchEvent(new Event(SIGNED_OUT_EVENT));
    }
    throw new ApiError(response.status, message, Number.isFinite(retry) && retry > 0 ? retry : null);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export const getHealth = () => apiFetch<Health>("/health", { cache: "no-store" });
