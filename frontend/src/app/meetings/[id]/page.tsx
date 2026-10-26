import { MeetingStatus } from "@/components/MeetingStatus";

export default async function MeetingPage({ params }: PageProps<"/meetings/[id]">) {
  const { id } = await params;
  return (
    <section className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <MeetingStatus captureId={id} />
    </section>
  );
}
