import type { Minutes, Segment } from "./types";

/** Fictional meeting used by the simulated API. Never real data. */
const LINES: [speaker: string, text: string][] = [
  ["Awa Example", "Hi everyone, let's start with the launch schedule."],
  ["Koffi Test", "I suggest we move the launch to March."],
  ["Awa Example", "Agreed, March it is. Koffi, can you prepare the backward plan by Friday?"],
  ["Koffi Test", "Yes, noted."],
  ["Speaker 3", "We will also need to review the budget, but we don't have the figures yet."],
];

export const MOCK_SEGMENT_COUNT = LINES.length;
export const MOCK_SEGMENT_INTERVAL_MS = 3000;

export function mockSegments(meetingId: string, count: number): Segment[] {
  return LINES.slice(0, count).map(([speaker, text], i) => ({
    meeting_id: meetingId,
    segment_id: `sim-${i}`,
    speaker,
    speaker_id: String((i % 3) + 1),
    start: i * 10,
    end: i * 10 + 8,
    text,
    language: "en",
    is_final: true,
  }));
}

export const MOCK_MINUTES: Minutes = {
  summary: "The team moves the launch to March and plans the next steps.",
  topics: [
    {
      title: "Launch schedule",
      summary: "The launch is moved to March.",
      source: { segment_indices: [0, 1, 2] },
    },
  ],
  decisions: [{ text: "Launch moved to March.", source: { segment_indices: [2] } }],
  actions: [
    {
      text: "Prepare the backward plan",
      owner: "Koffi Test",
      due_date: "Friday",
      source: { segment_indices: [2, 3] },
    },
    { text: "Review the budget", owner: null, due_date: null, source: { segment_indices: [4] } },
  ],
  open_points: [
    { text: "Budget figures are not available yet.", source: { segment_indices: [4] } },
  ],
};
