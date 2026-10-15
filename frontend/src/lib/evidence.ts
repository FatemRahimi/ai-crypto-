export type TechnicalRecord = {
  evidenceId: number;
  evidenceType: string;
  interval: string;
  observationTime: string;
  calculatorVersion: string;
  parameters: Record<string, unknown>;
  inputCandleCount: number;
  dataStatus: string;
  freshness: "fresh" | "stale" | "gap" | "insufficient" | "invalid";
  result: Record<string, unknown>;
  provider: string;
  providerSymbol: string;
};

export type EvidencePage = {
  records: TechnicalRecord[];
  empty: boolean;
};

const EVIDENCE_TYPES = new Set([
  "swing_structure",
  "support_resistance",
  "range_statistics",
  "candle_vwap",
]);

const BANNED_KEYS = new Set([
  "probability",
  "recommendation",
  "signal",
  "leverage",
  "expected_return",
  "side",
]);

const BANNED_TEXT = new Set(["BUY", "SELL", "LONG", "SHORT"]);

export function parseEvidencePage(value: unknown): EvidencePage | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const page = value as Record<string, unknown>;
  if (page.canonical_symbol !== "BTC/USDT" || !Array.isArray(page.records)) {
    return null;
  }
  const records: TechnicalRecord[] = [];
  for (const item of page.records) {
    const record = parseRecord(item);
    if (record) {
      records.push(record);
    }
  }
  if (page.records.length > 0 && records.length === 0) {
    return null;
  }
  return { records, empty: records.length === 0 };
}

function parseRecord(value: unknown): TechnicalRecord | null {
  if (typeof value !== "object" || value === null || containsBanned(value)) {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.evidence_id !== "number" ||
    typeof record.evidence_type !== "string" ||
    !EVIDENCE_TYPES.has(record.evidence_type) ||
    typeof record.interval !== "string" ||
    typeof record.observation_time !== "string" ||
    typeof record.calculator_version !== "string" ||
    typeof record.input_candle_count !== "number" ||
    typeof record.data_status !== "string" ||
    typeof record.provider !== "string" ||
    typeof record.provider_symbol !== "string" ||
    typeof record.parameters !== "object" ||
    record.parameters === null ||
    typeof record.result !== "object" ||
    record.result === null
  ) {
    return null;
  }
  if (
    record.freshness !== "fresh" &&
    record.freshness !== "stale" &&
    record.freshness !== "gap" &&
    record.freshness !== "insufficient" &&
    record.freshness !== "invalid"
  ) {
    return null;
  }
  return {
    evidenceId: record.evidence_id,
    evidenceType: record.evidence_type,
    interval: record.interval,
    observationTime: record.observation_time,
    calculatorVersion: record.calculator_version,
    parameters: record.parameters as Record<string, unknown>,
    inputCandleCount: record.input_candle_count,
    dataStatus: record.data_status,
    freshness: record.freshness,
    result: record.result as Record<string, unknown>,
    provider: record.provider,
    providerSymbol: record.provider_symbol,
  };
}

function containsBanned(value: unknown): boolean {
  if (typeof value === "string") {
    return BANNED_TEXT.has(value.trim().toUpperCase());
  }
  if (Array.isArray(value)) {
    return value.some((item) => containsBanned(item));
  }
  if (typeof value === "object" && value !== null) {
    return Object.entries(value).some(
      ([key, item]) => BANNED_KEYS.has(key) || containsBanned(item),
    );
  }
  return false;
}
