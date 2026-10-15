import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TechnicalEvidence } from "@/components/research/TechnicalEvidence";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TechnicalEvidence", () => {
  it("keeps the empty state when nothing is stored", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ canonical_symbol: "BTC/USDT", records: [] }),
      }),
    );
    render(<TechnicalEvidence />);
    expect(screen.getByText("No verified technical evidence")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("No verified technical evidence")).toBeInTheDocument();
    });
    expect(screen.queryByText(/LONG|SHORT|BUY|SELL/)).toBeNull();
  });

  it("shows a stored structure label and its source", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          canonical_symbol: "BTC/USDT",
          records: [
            {
              evidence_id: 4,
              evidence_type: "swing_structure",
              provider: "binance_spot",
              provider_symbol: "BTCUSDT",
              interval: "1m",
              observation_time: "2026-10-15T12:04:59.999000Z",
              calculator_version: "technical-evidence-v1",
              parameters: { left: 1, right: 1 },
              input_candle_count: 5,
              data_status: "VALID",
              freshness: "stale",
              result: { structure: [{ label: "higher_high", price: "10" }] },
            },
          ],
        }),
      }),
    );
    render(<TechnicalEvidence />);
    expect(await screen.findByText("Higher high 10")).toBeInTheDocument();
    expect(screen.getByText(/technical-evidence-v1/)).toBeInTheDocument();
    expect(screen.getByText(/Stale observation/)).toBeInTheDocument();
    expect(screen.queryByText(/LONG|SHORT|BUY|SELL/)).toBeNull();
  });
});