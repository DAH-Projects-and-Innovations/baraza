import type { Metadata } from "next";
import { LoginForm } from "@/components/LoginForm";
import { Logo } from "@/components/layout/Logo";

export const metadata: Metadata = { title: "Sign in · Baraza" };

const BARS = [18, 30, 46, 24, 56, 36, 50, 22, 40, 28, 52, 20, 34, 44, 16];

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-wrap bg-surface">
      <main className="flex min-w-0 flex-1 basis-130 flex-col justify-between gap-10 px-6 py-10 md:px-16 md:py-12">
        <Logo size={40} textClass="text-[26px]" />
        <div className="flex w-full max-w-105 flex-col gap-6 self-center">
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-[40px] leading-[1.1] font-extrabold tracking-[-0.025em]">Welcome back</h1>
            <p className="text-base leading-relaxed text-secondary">
              Sign in to read and validate your meeting minutes.
            </p>
          </div>
          <LoginForm />
        </div>
        <p className="max-w-105 self-center text-center text-[13px] leading-relaxed text-muted">
          Open source by DAH Labs. Your minutes stay on the server your organisation chooses.
        </p>
      </main>

      <aside className="relative flex min-h-105 min-w-0 flex-1 basis-120 flex-col justify-center gap-10 overflow-hidden bg-navy p-8 text-white md:p-12">
        <span aria-hidden="true" className="absolute -top-30 -right-40 h-130 w-130 rounded-full bg-[radial-gradient(circle,rgba(91,63,240,0.55),rgba(91,63,240,0)_70%)]" />
        <span aria-hidden="true" className="absolute -bottom-40 -left-40 h-120 w-120 rounded-full bg-[radial-gradient(circle,rgba(36,87,245,0.5),rgba(36,87,245,0)_70%)]" />
        <div className="relative flex max-w-130 flex-col gap-4">
          <h2 className="font-display text-[44px] leading-[1.1] font-extrabold tracking-[-0.025em]">
            Meetings end.<br />Decisions shouldn&apos;t disappear.
          </h2>
          <p className="text-[17px] leading-relaxed text-[#c3cdf0]">
            An assistant joins your Google Meet, writes the minutes, and you validate them. Nothing
            is shared until a human says so.
          </p>
        </div>
        <div className="relative flex max-w-130 flex-col gap-4 rounded-3xl border border-white/15 bg-white/8 p-6">
          <div className="flex h-14 items-end gap-1.25" aria-hidden="true">
            {BARS.map((height, i) => (
              <span key={i} className={`w-1.5 rounded-[3px] ${i % 2 === 0 && i % 3 !== 1 ? "bg-[#9b86ff]" : "bg-[#7fa6ff]"}`} style={{ height }} />
            ))}
          </div>
          <p className="font-serif text-[22px] leading-snug font-medium">
            “The committee agreed to launch the pilot in March.”
          </p>
          <div className="flex flex-wrap gap-2.5">
            <span className="rounded-full bg-white/12 px-3 py-1 text-[13px] font-semibold">3 decisions</span>
            <span className="rounded-full bg-white/12 px-3 py-1 text-[13px] font-semibold">5 actions</span>
            <span className="rounded-full bg-accent px-3 py-1 text-[13px] font-semibold text-foreground">Waiting for your review</span>
          </div>
        </div>
      </aside>
    </div>
  );
}
