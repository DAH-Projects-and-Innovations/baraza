import { StartMeetingForm } from "@/components/StartMeetingForm";
import { USE_MOCK_API } from "@/lib/config";

export default function NewMeetingPage() {
  return (
    <section className="mx-auto w-full max-w-xl px-4 py-10 sm:px-6 sm:py-14">
      <h1 className="text-2xl font-semibold tracking-tight">Start a meeting capture</h1>
      <p className="mt-1 mb-6 text-muted">
        {USE_MOCK_API ? "Try the capture flow with fictional data for the internal demo."
          : "Paste a Google Meet link to request the visible Baraza assistant."}
      </p>
      <StartMeetingForm />
    </section>
  );
}
