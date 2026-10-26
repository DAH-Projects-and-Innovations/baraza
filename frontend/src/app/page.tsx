import Link from "next/link";
import { API_URL } from "@/lib/config";

export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-16 sm:px-6 sm:py-24">
      <h1 className="text-4xl font-semibold tracking-tight">
        From meeting to <span className="text-brand">validated minutes</span>
      </h1>
      <p className="max-w-xl text-lg text-muted">
        Baraza joins your online meeting, transcribes it, and drafts structured minutes that you
        review before sharing.
      </p>
      <Link
        href="/meetings/new"
        className="self-start rounded-lg bg-brand px-5 py-2.5 font-medium text-white hover:bg-brand-strong"
      >
        Start a meeting capture
      </Link>
      <p className="text-xs text-faint">
        API: <code>{API_URL}</code>
      </p>
    </div>
  );
}
