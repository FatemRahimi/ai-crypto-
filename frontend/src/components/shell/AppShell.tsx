import type { ReactNode } from "react";
import { DemoBanner } from "@/components/shell/DemoBanner";
import { SideNav } from "@/components/shell/SideNav";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-10 focus:bg-sheet focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <DemoBanner />
      <div className="mx-auto grid max-w-[1440px] lg:grid-cols-[240px_minmax(0,1fr)]">
        <SideNav />
        <main id="content" className="px-5 py-8 lg:px-10 lg:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}
