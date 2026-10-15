export type MarketFreshness = "fresh" | "stale" | "unavailable";

export type VerifiedMarket = {
  canonicalSymbol: string;
  provider: string;
  providerSymbol: string;
  price: string;
  observationTime: string;
  freshness: "fresh" | "stale";
  detail: string;
};

export function parseVerifiedMarket(value: unknown): VerifiedMarket | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (record.canonical_symbol !== "BTC/USDT" || record.provider !== "binance_spot") {
    return null;
  }
  if (typeof record.price !== "string" || record.price.length === 0) {
    return null;
  }
  if (record.freshness !== "fresh" && record.freshness !== "stale") {
    return null;
  }
  if (typeof record.observation_time !== "string" || typeof record.provider_symbol !== "string") {
    return null;
  }
  if (typeof record.detail !== "string") {
    return null;
  }
  return {
    canonicalSymbol: "BTC/USDT",
    provider: "binance_spot",
    providerSymbol: record.provider_symbol,
    price: record.price,
    observationTime: record.observation_time,
    freshness: record.freshness,
    detail: record.detail,
  };
}
