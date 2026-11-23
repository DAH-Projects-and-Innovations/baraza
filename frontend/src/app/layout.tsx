import type { Metadata } from "next";
import { Inter, Newsreader, Plus_Jakarta_Sans } from "next/font/google";
import { AuthGate, AuthProvider } from "@/components/AuthProvider";
import { AppShell } from "@/components/layout/AppShell";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jakarta = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-jakarta" });
const newsreader = Newsreader({ subsets: ["latin"], variable: "--font-newsreader" });

export const metadata: Metadata = {
  title: "Baraza",
  description: "Meeting minutes your team can trust",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`h-full antialiased ${inter.variable} ${jakarta.variable} ${newsreader.variable}`}
    >
      <body className="min-h-full font-sans">
        <AuthProvider>
          <AppShell>
            <AuthGate>{children}</AuthGate>
          </AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
