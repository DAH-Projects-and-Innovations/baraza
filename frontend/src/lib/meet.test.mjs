import assert from "node:assert/strict";
import test from "node:test";
import { isGoogleMeetUrl, normalizeGoogleMeetUrl } from "./meet.ts";

test("accepts canonical and /meet/ links and normalizes the latter", () => {
  const canonical = "https://meet.google.com/abc-defg-hij?authuser=0";
  const alternate = " https://meet.google.com/meet/abc-defg-hij?authuser=0 ";
  assert.ok(isGoogleMeetUrl(canonical));
  assert.ok(isGoogleMeetUrl(alternate));
  assert.equal(normalizeGoogleMeetUrl(alternate), canonical);
});

test("rejects lookalike hosts, credentials, fragments and malformed codes", () => {
  for (const value of [
    "https://meet.google.com.attacker.example/abc-defg-hij",
    "https://meet.google.com@attacker.example/abc-defg-hij",
    "http://meet.google.com/abc-defg-hij", "https://meet.google.com/abc-def-hij",
    "https://meet.google.com/abc-defg-hij#hidden", "https://meet.google.com/abc-defg-hij? bad",
  ]) assert.equal(isGoogleMeetUrl(value), false, value);
});
