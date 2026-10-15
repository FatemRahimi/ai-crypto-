"use client";

import { useEffect, useState } from "react";
import { apiBaseUrl, parseLiveHealth } from "@/lib/health";

type Status = "checking" | "reachable" | "unreachable";

export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [environment, setEnvironment] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiBaseUrl()}/health/live`, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          setStatus("unreachable");
          return;
        }
        const parsed = parseLiveHealth(await response.json());
        if (!parsed) {
          setStatus("unreachable");
          return;
        }
        setEnvironment(parsed.environment);
        setStatus("reachable");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setStatus("unreachable");
      });
    return () => controller.abort();
  }, []);

  const label =
    status === "checking"
      ? "Checking"
      : status === "reachable"
        ? `Reachable (${environment ?? "unknown"})`
        : "Unreachable";

  return (
    <p className="text-muted text-sm" role="status">
      Local API: {label}. This check does not load market data.
    </p>
  );
}
