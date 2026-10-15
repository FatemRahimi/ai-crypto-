import { POSITION_ACTIONS } from "@/content/navigation";
import { POSITION_FIELDS } from "@/content/workspace";
import { EmptyNote, FieldList, PageHeader, Panel } from "@/components/ui/primitives";

export function PositionBoard() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Positions"
        title="Position management"
        summary="A position will be shown only after a fill is verified. None is on file. These controls cannot send an order."
      />
      <Panel title="Open position">
        <EmptyNote>No verified position.</EmptyNote>
        <div className="mt-4">
          <FieldList fields={POSITION_FIELDS} />
        </div>
      </Panel>
      <Panel title="Possible future actions">
        <div className="flex flex-wrap gap-2">
          {POSITION_ACTIONS.map((action) => (
            <button
              key={action}
              type="button"
              disabled
              className="border-line text-muted cursor-not-allowed rounded-md border px-3 py-2 text-sm"
            >
              {action}
            </button>
          ))}
        </div>
        <p className="text-muted mt-4 text-sm">
          Execution is not available. Selecting these actions is disabled, and they do nothing.
        </p>
      </Panel>
    </div>
  );
}
