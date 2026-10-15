"use client";

import { useEffect, useState } from "react";
import { apiBaseUrl } from "@/lib/health";
import { parseEvidencePage, type TechnicalRecord } from "@/lib/evidence";

type View =
  | { kind: "empty" }
  | { kind: "unavailable" }
  | { kind: "verified"; records: TechnicalRecord[] };

export function TechnicalEvidence() {
  const [view, setView] = useState<View>({ kind: "empty" });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${apiBaseUrl()}/api/v1/technical-evidence?symbol=BTC/USDT&interval=1m&limit=20`;
    fetch(url, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          setView({ kind: "unavailable" });
          return;
        }
        const page = parseEvidencePage(await response.json());
        if (!page || page.empty) {
          setView({ kind: "empty" });
          return;
        }
        setView({ kind: "verified", records: page.records });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setView({ kind: "unavailable" });
      });
    return () => controller.abort();
  }, []);

  if (view.kind === "unavailable") {
    return <p className="text-muted mt-3 text-sm">Technical evidence unavailable</p>;
  }
  if (view.kind === "empty") {
    return <p className="text-muted mt-3 text-sm">No verified technical evidence</p>;
  }
  return (
    <div className="mt-3 space-y-4">
      {view.records.map((record) => (
        <article key={record.evidenceId}>
          <p className="font-serif text-lg text-ink">BTC/USDT · {record.interval}</p>
          <p className="text-muted mt-1 text-sm">{labelFor(record.evidenceType)}</p>
          <Measurements record={record} />
          <p className="text-muted mt-2 text-sm">
            Source {record.provider} {record.providerSymbol}. Observation {record.observationTime}.
            Calculator {record.calculatorVersion}. {freshnessText(record.freshness)} Inputs{" "}
            {record.inputCandleCount}.
          </p>
        </article>
      ))}
    </div>
  );
}

function Measurements({ record }: { record: TechnicalRecord }) {
  if (record.freshness === "gap" || record.dataStatus === "GAP_DETECTED") {
    return <p className="mt-1 text-sm text-ink">Gap detected. No level was filled.</p>;
  }
  if (record.freshness === "insufficient" || record.dataStatus === "INSUFFICIENT") {
    return <p className="mt-1 text-sm text-ink">Insufficient verified candles.</p>;
  }
  if (record.freshness === "invalid" || record.dataStatus === "INVALID") {
    return <p className="mt-1 text-sm text-ink">The candle input was rejected.</p>;
  }
  if (record.evidenceType === "swing_structure") {
    return <StructureList result={record.result} />;
  }
  if (record.evidenceType === "support_resistance") {
    return <LevelList result={record.result} />;
  }
  if (record.evidenceType === "range_statistics") {
    return <RangeList result={record.result} />;
  }
  if (record.evidenceType === "candle_vwap") {
    return <VwapLine result={record.result} />;
  }
  return null;
}

function StructureList({ result }: { result: Record<string, unknown> }) {
  const structure = arrayOfRecords(result.structure);
  if (structure.length === 0) {
    return <p className="mt-1 text-sm text-ink">No confirmed structure comparison.</p>;
  }
  return (
    <ul className="mt-1 space-y-1 text-sm text-ink">
      {structure.map((item, index) => (
        <li key={`${String(item.label)}-${index}`}>
          {labelFor(String(item.label ?? ""))} {String(item.price ?? "")}
        </li>
      ))}
    </ul>
  );
}

function LevelList({ result }: { result: Record<string, unknown> }) {
  const levels = arrayOfRecords(result.levels);
  if (levels.length === 0) {
    return <p className="mt-1 text-sm text-ink">No confirmed level.</p>;
  }
  return (
    <ul className="mt-1 space-y-1 text-sm text-ink">
      {levels.map((item, index) => (
        <li key={`${String(item.role)}-${index}`}>
          {labelFor(String(item.role ?? ""))} {String(item.price ?? "")}. Touch count{" "}
          {String(item.touch_count ?? "")}.
        </li>
      ))}
    </ul>
  );
}

function RangeList({ result }: { result: Record<string, unknown> }) {
  return (
    <p className="mt-1 text-sm text-ink">
      High {text(result.high)}. Low {text(result.low)}. Range {text(result.range)}. Midpoint{" "}
      {text(result.midpoint)}. Percentage range {text(result.percentage_range)}.
    </p>
  );
}

function VwapLine({ result }: { result: Record<string, unknown> }) {
  return (
    <p className="mt-1 text-sm text-ink">
      Candle VWAP {text(result.vwap)}. Candle proxy, not a trade VWAP.
    </p>
  );
}

function arrayOfRecords(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => {
    return typeof item === "object" && item !== null;
  });
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "—";
}

function labelFor(value: string): string {
  const labels: Record<string, string> = {
    swing_structure: "Swing structure",
    support_resistance: "Support / resistance",
    range_statistics: "Range statistics",
    candle_vwap: "Candle VWAP",
    higher_high: "Higher high",
    higher_low: "Higher low",
    lower_high: "Lower high",
    lower_low: "Lower low",
    equal_high: "Equal high",
    equal_low: "Equal low",
    support: "Support",
    resistance: "Resistance",
  };
  return labels[value] ?? value;
}

function freshnessText(value: TechnicalRecord["freshness"]): string {
  if (value === "stale") {
    return "Stale observation.";
  }
  if (value === "fresh") {
    return "Fresh observation.";
  }
  if (value === "gap") {
    return "Gap detected.";
  }
  if (value === "insufficient") {
    return "Insufficient sample.";
  }
  return "Input rejected.";
}
