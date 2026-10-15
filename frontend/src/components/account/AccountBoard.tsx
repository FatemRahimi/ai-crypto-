import { ACCOUNT_SECTIONS } from "@/content/workspace";
import { PageHeader, Panel, PlannedTag } from "@/components/ui/primitives";

export function AccountBoard() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Account"
        title="Operator, not custodian"
        summary="Your funds stay at the exchange. AI-Crypto is not a wallet, and this phase does not ask for exchange credentials."
      />
      <div className="grid gap-4">
        {ACCOUNT_SECTIONS.map((section) => (
          <Panel
            key={section.title}
            title={section.title}
            aside={section.planned ? <PlannedTag /> : null}
          >
            <p className="text-sm leading-relaxed text-ink">{section.body}</p>
          </Panel>
        ))}
      </div>
    </div>
  );
}
