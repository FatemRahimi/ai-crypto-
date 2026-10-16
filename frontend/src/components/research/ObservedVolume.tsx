"use client";

import { useEffect, useState } from "react";
import { parseObservedVolume, type ObservedVolumeEvidence } from "@/lib/observedVolume";
import { apiBaseUrl } from "@/lib/health";

type View = { kind: "empty" } | { kind: "unavailable" } | ObservedVolumeEvidence;

export function ObservedVolume() {
  const [view, setView] = useState<View>({ kind: "empty" });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${apiBaseUrl()}/api/v1/observed-volume?symbol=BTC/USDT`;
    fetch(url, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          setView({ kind: "unavailable" });
          return;
        }
        const parsed = parseObservedVolume(await response.json());
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
    return (
      <p className="text-muted mt-3 text-sm">
        No observed volume-at-price evidence has been calculated or stored.
      </p>
    );
  }
  if (view.kind === "unavailable") {
    return (
      <p className="text-muted mt-3 text-sm">Observed volume-at-price evidence is unavailable.</p>
    );
  }
  return (
    <div className="mt-4">
      <p className="text-ink text-sm font-medium">Observed Volume at Price</p>
      {view.sufficiency === "OBSERVED" && view.observedPocPrice !== null ? (
        <>
          <p className="text-ink mt-2 text-sm">
            Observed Point of Control {view.observedPocPrice}
          </p>
          {view.pocTie && view.pocTieCount !== null ? (
            <p className="text-muted mt-1 text-sm">
              Tied observed point-of-control buckets: {view.pocTieCount}. The lower price is shown.
            </p>
          ) : null}
          {view.largestAggregateBaseQuantity !== null ? (
            <p className="text-muted mt-1 text-sm">
              Largest single aggregate base quantity {view.largestAggregateBaseQuantity}.
              {view.derivedLargestShare !== null
                ? ` Derived share of observed base volume ${view.derivedLargestShare}.`
                : ""}
            </p>
          ) : null}
          <ul className="text-muted mt-2 list-disc space-y-1 pl-5 text-sm">
            {view.buckets.map((bucket) => (
              <li key={bucket.price}>
                {bucket.price} observed base volume {bucket.observedBaseVolume}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <p className="text-muted mt-2 text-sm">{view.limitation}</p>
      <p className="text-muted mt-1 text-sm">Source completeness: {view.sourceCompleteness}</p>
    </div>
  );
}
