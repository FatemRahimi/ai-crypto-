"use client";

import { useEffect, useState } from "react";
import { parseAggregateReadiness } from "@/lib/aggregateTrades";
import { apiBaseUrl } from "@/lib/health";

type View = "empty" | "available" | "unavailable";

export function AggregateTradeReadiness() {
  const [view, setView] = useState<View>("empty");

  useEffect(() => {
    const controller = new AbortController();
    const url = `${apiBaseUrl()}/api/v1/market-data/aggregate-trade-windows?symbol=BTC/USDT`;
    fetch(url, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          setView("unavailable");
          return;
        }
        const readiness = parseAggregateReadiness(await response.json());
        if (readiness === "available") {
          setView("available");
          return;
        }
        setView(readiness === "empty" ? "empty" : "unavailable");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setView("unavailable");
      });
    return () => controller.abort();
  }, []);

  if (view === "available") {
    return (
      <p className="text-muted mt-3 text-sm">
        Stored observations available; clock-window completeness is not proven.
      </p>
    );
  }
  if (view === "unavailable") {
    return <p className="text-muted mt-3 text-sm">Aggregate trade data unavailable</p>;
  }
  return (
    <p className="text-muted mt-3 text-sm">
      No aggregate trades are stored. That is not proof the market was idle.
    </p>
  );
}
