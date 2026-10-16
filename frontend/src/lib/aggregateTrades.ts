const BANNED_KEYS = new Set([
  "poc",
  "vah",
  "val",
  "hvn",
  "lvn",
  "delta",
  "cvd",
  "signal",
  "probability",
  "recommendation",
]);

export type AggregateReadiness = "available" | "empty";

export function parseAggregateReadiness(value: unknown): AggregateReadiness | null {
  if (typeof value !== "object" || value === null || containsBanned(value)) {
    return null;
  }
  const page = value as Record<string, unknown>;
  if (page.canonical_symbol !== "BTC/USDT" || typeof page.stored_count !== "number") {
    return null;
  }
  if (page.stored_count > 0) {
    return "available";
  }
  if (page.stored_count === 0) {
    return "empty";
  }
  return null;
}

function containsBanned(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some((item) => containsBanned(item));
  }
  if (typeof value === "object" && value !== null) {
    return Object.entries(value).some(
      ([key, item]) => BANNED_KEYS.has(key.toLowerCase()) || containsBanned(item),
    );
  }
  return false;
}
