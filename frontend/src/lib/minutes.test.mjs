import assert from "node:assert/strict";
import test from "node:test";
import { actorLabel, countGaps, removeAt, replaceAt, sameMinutes, toOptional } from "./minutes.ts";

const minutes = {
  summary: "S",
  topics: [],
  decisions: [{ text: "D", source: { segment_indices: [0] } }],
  actions: [
    { text: "A1", owner: "Awa", due_date: "2026-11-20", source: { segment_indices: [1] } },
    { text: "A2", owner: null, due_date: null, source: { segment_indices: [2] } },
    { text: "A3", owner: "Koffi", due_date: null, source: { segment_indices: [2] } },
  ],
  open_points: [],
};

test("blank input becomes null, never an empty string", () => {
  assert.equal(toOptional("   "), null);
  assert.equal(toOptional(""), null);
  assert.equal(toOptional("  Awa Example "), "Awa Example");
});

test("counts the actions that still lack an owner or a deadline", () => {
  assert.deepEqual(countGaps(minutes), { ownerMissing: 1, dueMissing: 2 });
});

test("detects whether the draft was changed", () => {
  assert.ok(sameMinutes(minutes, structuredClone(minutes)));
  const changed = structuredClone(minutes);
  changed.actions[1].owner = "Nadia";
  assert.ok(!sameMinutes(minutes, changed));
});

test("removes and replaces by index without touching the original", () => {
  const list = ["a", "b", "c"];
  assert.deepEqual(removeAt(list, 1), ["a", "c"]);
  assert.deepEqual(replaceAt(list, 1, "x"), ["a", "x", "c"]);
  assert.deepEqual(list, ["a", "b", "c"]);
});

test("names the people who saved a version", () => {
  assert.equal(actorLabel("assistant"), "The assistant");
  assert.equal(actorLabel("local-user"), "You");
  assert.equal(actorLabel("awa@example.org"), "awa@example.org");
});
