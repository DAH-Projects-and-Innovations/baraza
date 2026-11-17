/** Pure helpers for sign in, free of React so they can be tested directly. */

/** Where to go after signing in. Only a path on this site: never another address. */
export function safeNext(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) {
    return "/";
  }
  if (value === "/login" || value.startsWith("/login?")) return "/";
  return value;
}

/** "Try again in 3 minutes", from the number of seconds the API asked us to wait. */
export function waitMessage(seconds: number | null): string {
  if (seconds === null || seconds <= 0) return "Too many attempts. Try again later.";
  if (seconds < 90) return `Too many attempts. Try again in ${seconds} seconds.`;
  const minutes = Math.ceil(seconds / 60);
  return `Too many attempts. Try again in ${minutes} minutes.`;
}

export function loginUrl(currentPath: string): string {
  const next = safeNext(currentPath);
  return next === "/" ? "/login" : `/login?next=${encodeURIComponent(next)}`;
}
