import type { Metadata } from "next";
import { ActionsView } from "@/components/ActionsView";

export const metadata: Metadata = { title: "Actions · Baraza" };

export default function ActionsPage() {
  return (
    <div className="flex max-w-4xl flex-col gap-6 px-5 py-8 md:px-14 md:py-10">
      <header className="flex flex-col gap-1.5">
        <h1 className="font-display text-4xl font-extrabold tracking-[-0.025em]">Actions</h1>
      </header>
      <ActionsView />
    </div>
  );
}
