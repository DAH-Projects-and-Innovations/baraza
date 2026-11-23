import assert from "node:assert/strict";
import test from "node:test";
import { exportFileName, minutesToMarkdown } from "./export.ts";

const minutes = {
  summary: "S",
  topics: [{ title: "T", summary: "TS", source: { segment_indices: [0] } }],
  decisions: [{ text: "D", source: { segment_indices: [0] } }],
  actions: [
    { text: "A1", owner: "Awa", due_date: "Friday", source: { segment_indices: [1] } },
    { text: "A2", owner: null, due_date: null, source: { segment_indices: [2] } },
  ],
  open_points: [],
};

test("markdown keeps missing owners and deadlines as not specified", () => {
  const md = minutesToMarkdown("Pilot", minutes);
  assert.match(md, /^# Pilot/);
  assert.match(md, /- \[ \] A1 \(owner: Awa, due: Friday\)/);
  assert.match(md, /- \[ \] A2 \(owner: not specified, due: not specified\)/);
  assert.match(md, /## Open points\n\n- not specified/);
});

test("file name is a safe slug", () => {
  assert.equal(exportFileName("Réunion: Budget Q4!"), "reunion-budget-q4.md");
  assert.equal(exportFileName("???"), "minutes.md");
});
