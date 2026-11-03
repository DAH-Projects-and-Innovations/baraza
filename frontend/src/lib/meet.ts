const MEET_URL = /^https:\/\/meet\.google\.com\/(?:meet\/)?[a-z]{3}-[a-z]{4}-[a-z]{3}(\?[^\s#]*)?$/;

export function normalizeGoogleMeetUrl(value: string): string {
  return value.trim().replace("https://meet.google.com/meet/", "https://meet.google.com/");
}

export function isGoogleMeetUrl(value: string): boolean {
  return MEET_URL.test(value.trim());
}
