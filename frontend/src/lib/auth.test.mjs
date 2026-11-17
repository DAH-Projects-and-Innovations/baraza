import assert from "node:assert/strict";
import test from "node:test";
import { loginUrl, safeNext, waitMessage } from "./auth.ts";

test("only a path on this site is a valid place to go after signing in", () => {
  assert.equal(safeNext("/meetings/abc"), "/meetings/abc");
  assert.equal(safeNext("/meetings/abc?x=1"), "/meetings/abc?x=1");
  for (const bad of [null, undefined, "", "https://evil.example", "//evil.example", "/\\evil", "evil"]) {
    assert.equal(safeNext(bad), "/");
  }
});

test("never sends the person back to the sign in page", () => {
  assert.equal(safeNext("/login"), "/");
  assert.equal(safeNext("/login?next=/x"), "/");
});

test("tells how long to wait", () => {
  assert.equal(waitMessage(null), "Too many attempts. Try again later.");
  assert.equal(waitMessage(45), "Too many attempts. Try again in 45 seconds.");
  assert.equal(waitMessage(600), "Too many attempts. Try again in 10 minutes.");
  assert.equal(waitMessage(601), "Too many attempts. Try again in 11 minutes.");
});

test("builds the sign in address with where to return", () => {
  assert.equal(loginUrl("/"), "/login");
  assert.equal(loginUrl("/meetings/abc"), "/login?next=%2Fmeetings%2Fabc");
  assert.equal(loginUrl("//evil.example"), "/login");
});
