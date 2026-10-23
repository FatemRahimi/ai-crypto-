"use client";

import { useEffect, useState } from "react";
import { parseFunding, type FundingEvidence as FundingView } from "@/lib/funding";
import { apiBaseUrl } from "@/lib/health";

type View = { kind: "empty" } | { kind: "unavailable" } | FundingView;

export function FundingEvidence() {
  const [view, setView] = useState<View>({ kind: "empty" });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${apiBaseUrl()}/api/v1/funding?symbol=BTCUSDT-PERP`;
    fetch(url, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          setView({ kind: "unavailable" });
          return;
        }
        const parsed = parseFunding(await response.json());
        setView(parsed ?? { kind: "unavailable" });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setView({ kind: "unavailable" });
      });
    return () => controller.abort();
  }, []);

  if (view.kind === "empty") {
    return <p className="text-muted mt-3 text-sm">No stored funding evidence is available.</p>;
  }
  if (view.kind === "unavailable") {
    return <p className="text-muted mt-3 text-sm">Funding evidence is unavailable.</p>;
  }
  return (
    <div className="mt-4">
      <p className="text-ink text-sm font-medium">{view.instrumentLabel}</p>
      <ul className="text-muted mt-2 list-disc space-y-1 pl-5 text-sm">
        {view.records.map((record) => (
          <li key={`${record.fundingTime}-${record.rateType}`}>
            Funding rate {record.fundingRate} at {record.fundingTime}. Rate type {record.rateType}.
          </li>
        ))}
      </ul>
      <p className="text-muted mt-2 text-sm">{view.limitation}</p>
      <p className="text-muted mt-1 text-sm">Source completeness: {view.completeness}</p>
    </div>
  );
}
