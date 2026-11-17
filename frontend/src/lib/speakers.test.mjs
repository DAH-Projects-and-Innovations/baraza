import assert from "node:assert/strict";
import test from "node:test";
import { isUnnamedSpeaker, knownNames, tidyName } from "./speakers.ts";

const line = (speaker) => ({ speaker });

test("recognises the labels the capture gives to speakers it cannot name", () => {
  assert.ok(isUnnamedSpeaker("Speaker 3"));
  assert.ok(isUnnamedSpeaker("Speaker 12"));
  for (const named of ["Awa Example", "speaker 3", "Speaker", "Speaker Three", "Speaker 3 bis"]) {
    assert.ok(!isUnnamedSpeaker(named));
  }
});

test("offers the names already in the transcript, once each, without the one being renamed", () => {
  const segments = [
    line("Awa Example"),
    line("Speaker 3"),
    line("Koffi Test"),
    line("Awa Example"),
    line("Speaker 4"),
  ];
  assert.deepEqual(knownNames(segments, "Speaker 3"), ["Awa Example", "Koffi Test"]);
  assert.deepEqual(knownNames(segments, "Awa Example"), ["Koffi Test"]);
});

test("tidies a name like the API does", () => {
  assert.equal(tidyName("  Nadia   M. "), "Nadia M.");
  assert.equal(tidyName("   "), null);
  assert.equal(tidyName("x".repeat(201)), null);
  assert.equal(tidyName("x".repeat(200)), "x".repeat(200));
});
