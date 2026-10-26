import { StartMeetingForm } from "@/components/StartMeetingForm";

export default function NewMeetingPage() {
  return (
    <section className="mx-auto w-full max-w-xl px-4 py-10 sm:px-6 sm:py-14">
      <h1 className="text-2xl font-semibold tracking-tight">Start a meeting capture</h1>
      <p className="mt-1 mb-6 text-muted">
        Paste a Google Meet link. A Baraza bot joins as a visible participant.
      </p>
      <StartMeetingForm />
    </section>
  );
}
