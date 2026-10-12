const MEET_URL = /^https:\/\/meet\.google\.com\/[a-z]{3}-[a-z]{4}-[a-z]{3}(\?.*)?$/;

export function isGoogleMeetUrl(value: string): boolean {
  return MEET_URL.test(value.trim());
}
