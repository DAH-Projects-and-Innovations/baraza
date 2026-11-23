import type { Metadata } from "next";
import { SettingsView } from "@/components/SettingsView";

export const metadata: Metadata = { title: "Settings · Baraza" };

export default function SettingsPage() {
  return (
    <div className="flex max-w-3xl flex-col gap-6 px-5 py-8 md:px-14 md:py-10">
      <header className="flex flex-col gap-1.5">
        <h1 className="font-display text-4xl font-extrabold tracking-[-0.025em]">Settings</h1>
        <p className="text-[15px] text-muted">Your account, your security and the assistant.</p>
      </header>
      <SettingsView />
    </div>
  );
}
