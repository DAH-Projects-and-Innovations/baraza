export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** When true, capture endpoints are simulated in the browser (backend not ready yet). */
export const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";
