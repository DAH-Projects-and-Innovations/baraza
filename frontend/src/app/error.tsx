"use client";

import Link from "next/link";

export default function ErrorPage({ retry }: { retry: () => void }) {
  return <section className="mx-auto max-w-3xl px-4 py-12">
    <h1 className="text-2xl font-semibold">This page could not be loaded</h1>
    <p role="alert" className="my-4 text-muted">Try again, or return to the new meeting page.</p>
    <button onClick={retry} className="mr-4 rounded-lg border border-brand px-3 py-2 text-brand">Try again</button>
    <Link href="/meetings/new" className="text-brand underline">New meeting</Link>
  </section>;
}
