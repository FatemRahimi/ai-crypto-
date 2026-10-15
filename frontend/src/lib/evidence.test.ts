import { describe, expect, it } from "vitest";
import { parseEvidencePage } from "@/lib/evidence";

const record = {
  evidence_id: 1,
  evidence_type: "swing_structure",
  canonical_symbol: "BTC/USDT",
  provider: "binance_spot",
  provider_symbol: "BTCUSDT",
  market_type: "spot",
  interval: "1m",
  observation_time: "2026-10-15T12:04:59.999000Z",
  calculated_at: "2026-10-15T12:10:00Z",
  calculator_name: "swing_structure",
  calculator_version: "technical-evidence-v1",
  parameters: { left: 1, right: 1, candle_limit: 10 },
  input_open_start: "2026-10-15T12:00:00Z",
  input_open_end: "2026-10-15T12:04:00Z",
  input_candle_count: 5,
  input_candle_ids: [1, 2, 3, 4, 5],
  result: {
    rule: "strict_fractal_confirmed_after_right_candles",
    structure: [{ label: "higher_high", price: "10" }],
  },
  data_status: "VALID",
  freshness: "stale",
};

describe("parseEvidencePage", () => {
  it("accepts sourced technical evidence", () => {
    expect(parseEvidencePage({ canonical_symbol: "BTC/USDT", records: [record] })).toMatchObject({
      empty: false,
      records: [{ evidenceType: "swing_structure", calculatorVersion: "technical-evidence-v1" }],
    });
  });

  it("rejects an empty store, a recommendation, and an unsourced payload", () => {
    expect(
      parseEvidencePage({
        canonical_symbol: "BTC/USDT",
        records: [],
        detail: "No verified technical evidence",
      }),
    ).toMatchObject({ empty: true, records: [] });
    expect(
      parseEvidencePage({
        canonical_symbol: "BTC/USDT",
        records: [{ ...record, result: { probability: "0.8", structure: [] } }],
      }),
    ).toBeNull();
    expect(parseEvidencePage({ records: [{ price: "100" }] })).toBeNull();
  });
});
