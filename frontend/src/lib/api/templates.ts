import { USE_MOCK_API } from "@/lib/config";
import { apiFetch } from "./client";

export interface MinutesTemplate {
  id: string;
  name: Record<string, string>;
  description: Record<string, string>;
  default: boolean;
}

/** The browser simulation only knows the standard template. */
const MOCK_TEMPLATES: MinutesTemplate[] = [
  {
    id: "standard",
    name: { en: "Standard" },
    description: { en: "Summary, decisions and actions." },
    default: true,
  },
];

export async function getTemplates(): Promise<MinutesTemplate[]> {
  if (USE_MOCK_API) return MOCK_TEMPLATES;
  return apiFetch<MinutesTemplate[]>("/templates", { cache: "no-store" });
}
