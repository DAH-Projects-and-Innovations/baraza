import Link from "next/link";

export default function NotFound() {
  return <section className="mx-auto max-w-3xl px-4 py-12">
    <h1 className="text-2xl font-semibold">Page not found</h1>
    <p className="my-4 text-muted">Check the address or start a new meeting capture.</p>
    <Link href="/meetings/new" className="text-brand underline">New meeting</Link>
  </section>;
}
