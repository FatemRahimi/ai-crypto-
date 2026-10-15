import { RESEARCH_SECTIONS } from "@/content/workspace";
import { EmptyNote, PageHeader } from "@/components/ui/primitives";

export function ResearchBoard() {
  return (
    <div>
      <PageHeader
        eyebrow="Research"
        title="Evidence, when it exists"
        summary="Advanced studies stay closed until you open them. None of these sections has a data source in Phase 1."
      />
      <div className="space-y-3">
        {RESEARCH_SECTIONS.map((section) => (
          <details key={section.id} className="border-line bg-sheet rounded-lg border px-5 py-4">
            <summary className="cursor-pointer font-serif text-xl text-ink">
              {section.title}
            </summary>
            <EmptyNote>
              <span className="mt-3 block">No evidence connected.</span>
            </EmptyNote>
            <ul className="text-muted mt-3 list-disc space-y-1 pl-5 text-sm">
              {section.topics.map((topic) => (
                <li key={topic}>{topic}</li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </div>
  );
}
