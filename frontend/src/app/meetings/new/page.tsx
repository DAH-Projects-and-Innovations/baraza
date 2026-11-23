import { StartMeetingForm } from "@/components/StartMeetingForm";
import { USE_MOCK_API } from "@/lib/config";

export default function NewMeetingPage() {
  return (
    <section className="w-full max-w-2xl px-5 py-8 md:px-14 md:py-10">
      <h1 className="font-display text-4xl font-extrabold tracking-[-0.025em]">Start a meeting capture</h1>
      <p className="mt-2 mb-8 text-[15px] leading-relaxed text-secondary">
        {USE_MOCK_API
          ? "Try the capture flow with fictional data for the internal demo."
          : "Paste a Google Meet link to request the visible Baraza assistant."}
      </p>
      <StartMeetingForm />
    </section>
  );
}
