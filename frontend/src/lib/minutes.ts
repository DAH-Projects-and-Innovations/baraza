import type { Minutes } from "./api/types";

/** Pure helpers for editing minutes, free of React so they can be tested directly. */

/** Blank input means "not specified": the backend stores null, never an empty string. */
export function toOptional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export function sameMinutes(a: Minutes, b: Minutes): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** Actions a reviewer should look at before validating. */
export function countGaps(minutes: Minutes): { ownerMissing: number; dueMissing: number } {
  return {
    ownerMissing: minutes.actions.filter((a) => !a.owner).length,
    dueMissing: minutes.actions.filter((a) => !a.due_date).length,
  };
}

export function removeAt<T>(items: T[], index: number): T[] {
  return items.filter((_, i) => i !== index);
}

export function replaceAt<T>(items: T[], index: number, value: T): T[] {
  return items.map((item, i) => (i === index ? value : item));
}

/** "assistant" and the placeholder user get readable names; anything else is shown as is. */
export function actorLabel(actor: string): string {
  if (actor === "assistant") return "The assistant";
  if (actor === "local-user") return "You";
  return actor;
}
