import Link from "next/link";
import { MeetingList } from "@/components/MeetingList";

export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10 sm:px-6 sm:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-tight">Meetings</h1>
          <p className="max-w-xl text-muted">
            Every meeting the assistant attended. Review the minutes, then validate them.
          </p>
        </div>
        <Link
          href="/meetings/new"
          className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-strong"
        >
          Start a meeting capture
        </Link>
      </div>
      <MeetingList />
    </div>
  );
}
