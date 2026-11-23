import { MeetingStatus } from "@/components/MeetingStatus";

export default async function MeetingPage({ params }: PageProps<"/meetings/[id]">) {
  const { id } = await params;
  return (
    <section className="w-full max-w-5xl px-5 py-8 md:px-12 md:py-8">
      <MeetingStatus key={id} captureId={id} />
    </section>
  );
}
