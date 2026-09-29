export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-6 py-24">
      <h1 className="text-3xl font-semibold tracking-tight">Baraza</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        From meeting transcript to validated meeting minutes.
      </p>
      <p className="text-sm text-zinc-500">
        The interface is under construction. The API is available at{" "}
        <code>{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</code>.
      </p>
    </main>
  );
}
