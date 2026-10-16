export type FundingRecord = {
  fundingTime: string;
  fundingRate: string;
  rateType: string;
};

export type FundingEvidence = {
  kind: "evidence";
  instrumentLabel: string;
  completeness: string;
  limitation: string;
  records: FundingRecord[];
};

export type FundingState = { kind: "empty" } | FundingEvidence;

const BANNED_KEYS = new Set([
  "bullish",
  "bearish",
  "crowded",
  "signal",
  "probability",
  "regime",
  "opportunity",
  "leverage",
]);

export function parseFunding(value: unknown): FundingState | null {
  if (!isRecord(value) || hasBannedKey(value)) {
    return null;
  }
  if (value.empty === true) {
    return Array.isArray(value.records) && value.records.length === 0 ? { kind: "empty" } : null;
  }
  if (!Array.isArray(value.records) || value.records.length === 0) {
    return null;
  }
  if (typeof value.instrument_label !== "string" || typeof value.limitation !== "string") {
    return null;
  }
  if (typeof value.completeness !== "string") {
    return null;
  }
  const records: FundingRecord[] = [];
  for (const item of value.records) {
    if (!isRecord(item) || hasBannedKey(item)) {
      return null;
    }
    if (
      typeof item.funding_time !== "string" ||
      typeof item.funding_rate !== "string" ||
      typeof item.rate_type !== "string"
    ) {
      return null;
    }
    records.push({
      fundingTime: item.funding_time,
      fundingRate: item.funding_rate,
      rateType: item.rate_type,
    });
  }
  return {
    kind: "evidence",
    instrumentLabel: value.instrument_label,
    completeness: value.completeness,
    limitation: value.limitation,
    records,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function hasBannedKey(value: Record<string, unknown>): boolean {
  return Object.keys(value).some((key) => BANNED_KEYS.has(key.toLowerCase()));
}
