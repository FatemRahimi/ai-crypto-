export type ObservedBucket = {
  price: string;
  observedBaseVolume: string;
  aggregateCount: number;
};

export type ObservedVolumeEvidence = {
  kind: "evidence";
  sufficiency: "OBSERVED" | "INSUFFICIENT" | "INVALID";
  limitation: string;
  observedPocPrice: string | null;
  pocTieCount: number | null;
  pocTie: boolean | null;
  sourceCompleteness: string;
  largestAggregateBaseQuantity: string | null;
  derivedLargestShare: string | null;
  buckets: ObservedBucket[];
};

export type ObservedVolumeState = { kind: "empty" } | ObservedVolumeEvidence;

const BANNED_KEYS = new Set([
  "vah",
  "val",
  "hvn",
  "lvn",
  "tpo",
  "delta",
  "cvd",
  "signal",
  "probability",
  "recommendation",
  "long",
  "short",
  "side",
  "leverage",
]);

export function parseObservedVolume(value: unknown): ObservedVolumeState | null {
  if (typeof value !== "object" || value === null || hasBannedKey(value)) {
    return null;
  }
  const page = value as Record<string, unknown>;
  if (page.empty === true) {
    return Array.isArray(page.records) && page.records.length === 0 ? { kind: "empty" } : null;
  }
  if (!Array.isArray(page.records) || page.records.length === 0) {
    return null;
  }
  const newest: unknown = page.records[0];
  if (typeof newest !== "object" || newest === null || hasBannedKey(newest)) {
    return null;
  }
  const record = newest as Record<string, unknown>;
  if (
    (record.sufficiency !== "OBSERVED" &&
      record.sufficiency !== "INSUFFICIENT" &&
      record.sufficiency !== "INVALID") ||
    typeof record.source_limitation !== "string" ||
    typeof record.source_completeness !== "string"
  ) {
    return null;
  }
  const poc = record.observed_poc_price;
  const tieCount = record.poc_tie_count;
  const tie = record.poc_tie;
  if (poc !== null && typeof poc !== "string") {
    return null;
  }
  if (tieCount !== null && typeof tieCount !== "number") {
    return null;
  }
  if (tie !== null && typeof tie !== "boolean") {
    return null;
  }
  const buckets = parseBuckets(record.buckets);
  if (buckets === null) {
    return null;
  }
  const largest = record.largest_aggregate_base_quantity;
  const share = record.derived_largest_aggregate_share_of_observed_base_volume;
  if (largest !== null && typeof largest !== "string") {
    return null;
  }
  if (share !== null && typeof share !== "string") {
    return null;
  }
  return {
    kind: "evidence",
    sufficiency: record.sufficiency,
    limitation: record.source_limitation,
    observedPocPrice: poc,
    pocTieCount: tieCount,
    pocTie: tie,
    sourceCompleteness: record.source_completeness,
    largestAggregateBaseQuantity: largest,
    derivedLargestShare: share,
    buckets,
  };
}

function parseBuckets(value: unknown): ObservedBucket[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const buckets: ObservedBucket[] = [];
  for (const item of value) {
    if (typeof item !== "object" || item === null) {
      return null;
    }
    const bucket = item as Record<string, unknown>;
    if (
      typeof bucket.price !== "string" ||
      typeof bucket.observed_base_volume !== "string" ||
      typeof bucket.aggregate_count !== "number"
    ) {
      return null;
    }
    buckets.push({
      price: bucket.price,
      observedBaseVolume: bucket.observed_base_volume,
      aggregateCount: bucket.aggregate_count,
    });
  }
  return buckets;
}

function hasBannedKey(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some((item) => hasBannedKey(item));
  }
  if (typeof value !== "object" || value === null) {
    return false;
  }
  return Object.entries(value).some(
    ([key, item]) => BANNED_KEYS.has(key.toLowerCase()) || hasBannedKey(item),
  );
}
