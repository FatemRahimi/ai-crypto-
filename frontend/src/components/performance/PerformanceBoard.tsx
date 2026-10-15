import { PERFORMANCE_SECTIONS } from "@/content/workspace";
import { EmptyNote, PageHeader, Panel } from "@/components/ui/primitives";

export function PerformanceBoard() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Performance"
        title="Recorded results only"
        summary="No performance has been calculated. This page will not draw a sample equity curve or invent a trading record."
      />
      <div className="grid gap-4 md:grid-cols-2">
        {PERFORMANCE_SECTIONS.map((title) => (
          <Panel key={title} title={title}>
            <EmptyNote>No verified history.</EmptyNote>
          </Panel>
        ))}
      </div>
    </div>
  );
}
