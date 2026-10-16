import { AggregateTradeReadiness } from "@/components/research/AggregateTradeReadiness";
import { ObservedVolume } from "@/components/research/ObservedVolume";
import { RESEARCH_SECTIONS } from "@/content/workspace";
import { TechnicalEvidence } from "@/components/research/TechnicalEvidence";
import { EmptyNote, PageHeader } from "@/components/ui/primitives";

export function ResearchBoard() {
  return (
    <div>
      <PageHeader
        eyebrow="Research"
        title="Evidence, when it exists"
        summary="Technical measurements appear only when a stored calculator result exists. The other sections have no data source."
      />
      <div className="space-y-3">
        {RESEARCH_SECTIONS.map((section) => (
          <details key={section.id} className="border-line bg-sheet rounded-lg border px-5 py-4">
            <summary className="cursor-pointer font-serif text-xl text-ink">
              {section.title}
            </summary>
            {section.id === "technical" ? (
              <TechnicalEvidence />
            ) : section.id === "profile" ? (
              <>
                <AggregateTradeReadiness />
                <ObservedVolume />
              </>
            ) : (
              <EmptyNote>
                <span className="mt-3 block">No evidence connected.</span>
              </EmptyNote>
            )}
            {section.id === "profile" ? null : (
              <ul className="text-muted mt-3 list-disc space-y-1 pl-5 text-sm">
                {section.topics.map((topic) => (
                  <li key={topic}>{topic}</li>
                ))}
              </ul>
            )}
            {section.id === "technical" ? (
              <p className="text-muted mt-3 text-sm">
                Supply, demand, liquidity, and Fibonacci are not calculated.
              </p>
            ) : null}
          </details>
        ))}
      </div>
    </div>
  );
}
