import type { Metadata } from "next";
import { LoginForm } from "@/components/LoginForm";

export const metadata: Metadata = { title: "Sign in · Baraza" };

export default function LoginPage() {
  return (
    <section className="mx-auto w-full max-w-sm px-4 py-12 sm:py-20">
      <h1 className="text-3xl font-semibold tracking-tight">Welcome back</h1>
      <p className="mt-2 mb-8 text-muted">Sign in to read and validate your meeting minutes.</p>
      <LoginForm />
    </section>
  );
}
