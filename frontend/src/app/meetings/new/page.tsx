import { StartMeetingForm } from "@/components/StartMeetingForm";

export default function NewMeetingPage() {
  return (
    <section className="mx-auto w-full max-w-3xl px-6 py-12">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">New meeting</h1>
      <StartMeetingForm />
    </section>
  );
}
