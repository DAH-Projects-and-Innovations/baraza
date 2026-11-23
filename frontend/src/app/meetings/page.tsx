import Link from "next/link";
import { MeetingLibrary } from "@/components/MeetingList";

export default function MeetingsPage() {
  return (
    <div className="flex flex-col gap-6 px-5 py-8 md:px-14 md:py-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-4xl font-extrabold tracking-[-0.025em]">Meetings</h1>
          <p className="text-[15px] text-muted">
            Every meeting the assistant attended. To add one, send the assistant from Google Meet.
          </p>
        </div>
        <Link href="/meetings/new" className="btn btn-primary">
          Start a meeting capture
        </Link>
      </header>
      <MeetingLibrary />
    </div>
  );
}
