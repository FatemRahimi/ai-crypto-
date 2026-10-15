"use client";

import { type FormEvent, useState } from "react";
import { PageHeader, Panel } from "@/components/ui/primitives";

type RiskPreference = "low" | "medium" | "high";

const inputClass = "border-line mt-2 w-full rounded-md border bg-sheet px-3 py-2 text-sm text-ink";

export function StrategyStudio() {
  const [capital, setCapital] = useState("");
  const [objective, setObjective] = useState("");
  const [risk, setRisk] = useState<RiskPreference | "">("");
  const [style, setStyle] = useState("");
  const [instrument, setInstrument] = useState("");
  const [allowLong, setAllowLong] = useState(false);
  const [allowShort, setAllowShort] = useState(false);
  const [rules, setRules] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("This intent stayed in the page. It was not sent, saved, compiled, or validated.");
  }

  return (
    <div>
      <PageHeader
        eyebrow="Strategy"
        title="Human and AI strategy design"
        summary="Describe intent here. Phase 1 does not compile it, score it, or approve it. A desired return is a preference, not a forecast."
      />
      <form className="grid gap-4 lg:grid-cols-2" onSubmit={onSubmit} autoComplete="off">
        <Panel title="My Strategy">
          <label className="block text-sm text-ink" htmlFor="capital">
            Capital context
          </label>
          <input
            id="capital"
            value={capital}
            onChange={(event) => setCapital(event.target.value)}
            className={inputClass}
            placeholder="For example, a future note about capital"
          />
          <label className="mt-4 block text-sm text-ink" htmlFor="instrument">
            Market preference
          </label>
          <input
            id="instrument"
            value={instrument}
            onChange={(event) => setInstrument(event.target.value)}
            className={inputClass}
            placeholder="For example, BTC perpetual futures"
          />
          <label className="mt-4 block text-sm text-ink" htmlFor="rules">
            Strategy rules
          </label>
          <textarea
            id="rules"
            value={rules}
            onChange={(event) => setRules(event.target.value)}
            rows={5}
            className={inputClass}
            placeholder="Rules you would want compiled later"
          />
        </Panel>
        <div className="space-y-4">
          <Panel title="Risk Preference">
            <fieldset>
              <legend className="text-sm text-ink">Preferred band</legend>
              <div className="mt-3 flex flex-wrap gap-4 text-sm">
                {(["low", "medium", "high"] as const).map((option) => (
                  <label key={option} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="risk"
                      value={option}
                      checked={risk === option}
                      onChange={() => setRisk(option)}
                    />
                    <span className="capitalize">{option}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </Panel>
          <Panel title="Trading Style">
            <label className="block text-sm text-ink" htmlFor="style">
              Style
            </label>
            <select
              id="style"
              value={style}
              onChange={(event) => setStyle(event.target.value)}
              className={inputClass}
            >
              <option value="">Not chosen</option>
              <option value="discretionary">Discretionary, with written rules</option>
              <option value="systematic">Systematic</option>
            </select>
          </Panel>
          <Panel title="Long / Short permissions">
            <div className="flex flex-col gap-2 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={allowLong}
                  onChange={(event) => setAllowLong(event.target.checked)}
                />
                Long allowed
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={allowShort}
                  onChange={(event) => setAllowShort(event.target.checked)}
                />
                Short allowed
              </label>
            </div>
          </Panel>
        </div>
        <Panel title="Desired return objective">
          <label className="block text-sm text-ink" htmlFor="objective">
            Objective
          </label>
          <input
            id="objective"
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
            className={inputClass}
            placeholder="A target you may state later"
          />
          <p className="text-muted mt-3 text-sm">
            A target is not an expected return. Nothing is calculated in Phase 1.
          </p>
        </Panel>
        <Panel title="AI Strategy Proposal">
          <p className="text-sm text-ink">No proposal.</p>
          <p className="text-muted mt-2 text-sm">
            Strategy compilation is not connected. The model cannot turn this form into rules yet.
          </p>
        </Panel>
        <Panel title="Quant Validation status">
          <p className="text-sm text-ink">Not run</p>
          <p className="text-muted mt-2 text-sm">
            There is no validation record because no strategy has been compiled.
          </p>
        </Panel>
        <Panel title="Approve Strategy">
          <button
            type="submit"
            className="border-moss text-moss rounded-md border px-4 py-2 text-sm"
          >
            Keep intent on this page
          </button>
          <button
            type="button"
            disabled
            className="border-line text-muted mt-3 block cursor-not-allowed rounded-md border px-4 py-2 text-sm"
          >
            Approve strategy
          </button>
          <p className="text-muted mt-3 text-sm">
            Approval is disabled. Refreshing the page clears the form. Nothing is stored.
          </p>
          {notice ? (
            <p className="border-line mt-4 border-t pt-3 text-sm text-ink" role="status">
              {notice}
            </p>
          ) : null}
        </Panel>
      </form>
    </div>
  );
}
