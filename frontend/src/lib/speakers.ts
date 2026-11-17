import type { Segment } from "./api/types";

/** The capture labels speakers it cannot name "Speaker 1", "Speaker 2", ... */
export function isUnnamedSpeaker(speaker: string): boolean {
  return /^Speaker \d+$/.test(speaker);
}

/** Names already in the transcript, offered as quick choices (a label is often one of them). */
export function knownNames(segments: Segment[], excluding: string): string[] {
  const names: string[] = [];
  for (const { speaker } of segments) {
    if (speaker !== excluding && !isUnnamedSpeaker(speaker) && !names.includes(speaker)) {
      names.push(speaker);
    }
  }
  return names;
}

/** Same rule as the API: tidy spaces, 1 to 200 characters. `null` when it cannot be used. */
export function tidyName(value: string): string | null {
  const name = value.split(/\s+/).filter(Boolean).join(" ");
  return name === "" || name.length > 200 ? null : name;
}
