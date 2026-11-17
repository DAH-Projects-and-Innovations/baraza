import { USE_MOCK_API } from "@/lib/config";
import { ApiError, apiFetch } from "./client";

export interface User {
  id: string;
  email: string;
  name: string;
}

/** The browser simulation has no accounts: everyone is the same fictional person. */
const SIMULATION_USER: User = { id: "simulation", email: "simulation", name: "Simulation" };

/** The signed in person, or `null` when there is no session. */
export async function getCurrentUser(): Promise<User | null> {
  if (USE_MOCK_API) return SIMULATION_USER;
  try {
    return await apiFetch<User>("/auth/me", { cache: "no-store" });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function signIn(email: string, password: string) {
  return apiFetch<User>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function signOut(): Promise<void> {
  if (USE_MOCK_API) return;
  await apiFetch("/auth/logout", { method: "POST" });
}

export function changePassword(currentPassword: string, newPassword: string) {
  return apiFetch<void>("/auth/password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}
