"use client";

import { useEffect, useState } from "react";
import { apiBaseUrl } from "@/lib/health";
import { parseVerifiedMarket, type VerifiedMarket } from "@/lib/market";

type View =
  | { kind: "checking" }
  | { kind: "empty" }
  | { kind: "unavailable" }
  | { kind: "verified"; market: VerifiedMarket };

export function VerifiedMarket() {
  const [view, setView] = useState<View>({ kind: "checking" });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiBaseUrl()}/api/v1/market-data/latest?symbol=BTC/USDT&interval=1m`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) {
          setView({ kind: "unavailable" });
          return;
        }
        const market = parseVerifiedMarket(await response.json());
        setView(market ? { kind: "verified", market } : { kind: "empty" });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setView({ kind: "unavailable" });
      });
    return () => controller.abort();
  }, []);

  return (
    <div>
      <p className="text-muted text-xs tracking-[0.14em] uppercase">01</p>
      <p className="mt-2 text-sm text-ink">What is BTC doing?</p>
      {view.kind === "verified" ? (
        <div className="mt-2">
          <p className="font-serif text-lg text-moss">{view.market.canonicalSymbol}</p>
          <p className="mt-1 font-serif text-2xl text-ink">{view.market.price}</p>
          <p className="text-muted mt-2 text-sm">
            Source {view.market.provider} {view.market.providerSymbol}. Observation{" "}
            {view.market.observationTime}.{" "}
            {view.market.freshness === "stale" ? "Stale observation." : "Fresh observation."}
          </p>
        </div>
      ) : (
        <p className="mt-2 font-serif text-lg text-moss">
          {view.kind === "unavailable" ? "Market data unavailable" : "No verified market data"}
        </p>
      )}
    </div>
  );
}
