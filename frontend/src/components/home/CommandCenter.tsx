import { ApiStatus } from "@/components/home/ApiStatus";
import { ChartWorkspace } from "@/components/home/ChartWorkspace";
import { CopilotPanel } from "@/components/home/CopilotPanel";
import { VerifiedMarket } from "@/components/home/VerifiedMarket";
import { PageHeader, Panel } from "@/components/ui/primitives";
import { StatusVocabulary } from "@/components/ui/StatusVocabulary";
import { COMMAND_QUESTIONS, DEMO_PANELS } from "@/content/home";

export function CommandCenter() {
  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div className="space-y-8">
        <PageHeader
          eyebrow="Command center"
          title="What needs attention"
          summary="These answers are the Phase 1 state of the system. The panels below are a demonstration layout, marked so they cannot be read as a live book."
        />
        <ApiStatus />
        <ol className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <li className="border-moss border-t pt-3">
            <VerifiedMarket />
          </li>
          {COMMAND_QUESTIONS.slice(1).map((item, index) => (
            <li key={item.question} className="border-moss border-t pt-3">
              <p className="text-muted text-xs tracking-[0.14em] uppercase">0{index + 2}</p>
              <p className="mt-2 text-sm text-ink">{item.question}</p>
              <p className="mt-2 font-serif text-lg text-moss">{item.answer}</p>
            </li>
          ))}
        </ol>
        <div>
          <h2 className="font-serif text-2xl text-ink">Demonstration layout</h2>
          <p className="text-muted mt-2 max-w-3xl text-sm leading-relaxed">
            Every value in this group is sample copy. It is not a price, a signal, a probability, or
            an account figure.
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {DEMO_PANELS.map((panel) => (
              <Panel key={panel.title} title={panel.title} demo>
                {panel.title === "AI View" ? (
                  <div className="mb-3">
                    <StatusVocabulary sample="WAIT" />
                  </div>
                ) : null}
                <p className="font-serif text-2xl text-ink">{panel.value}</p>
                <p className="text-muted mt-2 text-sm leading-relaxed">{panel.detail}</p>
                {panel.title === "Weekly Goal / Progress" ? (
                  <div className="mt-4">
                    <div className="bg-line h-1.5 rounded-full" aria-hidden="true">
                      <div className="bg-demo/70 h-1.5 w-1/3 rounded-full" />
                    </div>
                    <p className="text-muted mt-2 text-xs">
                      Sample marker. This is not measured progress.
                    </p>
                  </div>
                ) : null}
              </Panel>
            ))}
          </div>
        </div>
        <ChartWorkspace />
      </div>
      <CopilotPanel />
    </div>
  );
}
