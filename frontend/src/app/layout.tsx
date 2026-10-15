import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "AI-Crypto",
    template: "%s · AI-Crypto",
  },
  description:
    "Personal adaptive AI-quant futures trading intelligence. Phase 1 is a local foundation, not a trading system.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
