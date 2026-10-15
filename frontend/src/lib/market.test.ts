import { describe, expect, it } from "vitest";
import { parseVerifiedMarket } from "@/lib/market";

describe("parseVerifiedMarket", () => {
  it("accepts a sourced price", () => {
    expect(
      parseVerifiedMarket({
        canonical_symbol: "BTC/USDT",
        provider: "binance_spot",
        provider_symbol: "BTCUSDT",
        price: "64000.10",
        observation_time: "2026-10-15T12:00:59+00:00",
        freshness: "stale",
        detail: "Verified public trade",
      }),
    ).toMatchObject({
      price: "64000.10",
      freshness: "stale",
      providerSymbol: "BTCUSDT",
    });
  });

  it("rejects an empty or unsourced payload", () => {
    expect(parseVerifiedMarket({ price: "1" })).toBeNull();
    expect(
      parseVerifiedMarket({
        canonical_symbol: "BTC/USDT",
        provider: "binance_spot",
        price: null,
        freshness: "unavailable",
      }),
    ).toBeNull();
  });
});
