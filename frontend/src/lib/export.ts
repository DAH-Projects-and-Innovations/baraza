import type { Minutes } from "./api/types";

/** Pure helpers to export validated minutes, free of React so they can be tested directly. */

const NOT_SPECIFIED = "not specified";

/** The minutes as Markdown. What is missing stays "not specified": nothing is invented. */
export function minutesToMarkdown(title: string, minutes: Minutes): string {
  const lines: string[] = [`# ${title}`, "", minutes.summary, ""];
  if (minutes.topics.length > 0) {
    lines.push("## Topics", "");
    for (const t of minutes.topics) lines.push(`- **${t.title}**: ${t.summary}`);
    lines.push("");
  }
  lines.push("## Decisions", "");
  if (minutes.decisions.length === 0) lines.push(`- ${NOT_SPECIFIED}`);
  for (const d of minutes.decisions) lines.push(`- ${d.text}`);
  lines.push("", "## Actions", "");
  if (minutes.actions.length === 0) lines.push(`- ${NOT_SPECIFIED}`);
  for (const a of minutes.actions) {
    lines.push(`- [ ] ${a.text} (owner: ${a.owner ?? NOT_SPECIFIED}, due: ${a.due_date ?? NOT_SPECIFIED})`);
  }
  lines.push("", "## Open points", "");
  if (minutes.open_points.length === 0) lines.push(`- ${NOT_SPECIFIED}`);
  for (const p of minutes.open_points) lines.push(`- ${p.text}`);
  lines.push("");
  return lines.join("\n");
}

/** A safe file name for the download. */
export function exportFileName(title: string): string {
  const slug = title
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return `${slug || "minutes"}.md`;
}
