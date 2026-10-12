import { MeetingStatus } from "@/components/MeetingStatus";

export default async function MeetingPage({ params }: PageProps<"/meetings/[id]">) {
  const { id } = await params;
  return (
    <section className="mx-auto w-full max-w-3xl px-6 py-12">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Meeting</h1>
      <MeetingStatus captureId={id} />
    </section>
  );
}
