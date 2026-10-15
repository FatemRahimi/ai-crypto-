import { PageHeader, Panel, FieldList, EmptyNote } from "@/components/ui/primitives";
import { StatusVocabulary } from "@/components/ui/StatusVocabulary";
import { OPPORTUNITY_FIELDS } from "@/content/workspace";

export function OpportunityBoard() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Opportunities"
        title="Candidate states"
        summary="An opportunity is a candidate, not an order. Phase 1 has not evaluated one, and this page does not assign probabilities."
      />
      <Panel title="Status vocabulary">
        <StatusVocabulary />
        <EmptyNote>
          <span className="mt-3 block">The current state is not evaluated.</span>
        </EmptyNote>
      </Panel>
      <Panel title="Layout sample" demo>
        <p className="mb-3 text-sm text-ink">Sample card. This is not an opportunity.</p>
        <FieldList fields={OPPORTUNITY_FIELDS} />
        <p className="text-muted mt-3 text-sm">
          Quant status: not evaluated. Risk status: not evaluated.
        </p>
      </Panel>
    </div>
  );
}
