import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FundingEvidence } from "@/components/research/FundingEvidence";

const LIMITATION =
  "Stored funding observations are available. Complete historical funding coverage is not proven.";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("FundingEvidence", () => {
  it("does not treat a missing store as a zero funding rate", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ empty: true, records: [] }),
      })),
    );
    render(<FundingEvidence />);
    expect(await screen.findByText("No stored funding evidence is available.")).toBeInTheDocument();
    expect(screen.queryByText(/funding was zero/i)).toBeNull();
  });

  it("shows the perpetual instrument, rate, time, and coverage limitation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          empty: false,
          instrument_label: "Binance USD-M BTCUSDT perpetual",
          completeness: "COMPLETENESS_UNKNOWN",
          limitation: LIMITATION,
          records: [
            {
              funding_time: "2026-10-16T16:00:00Z",
              funding_rate: "-0.03750000",
              rate_type: "Regular",
            },
          ],
        }),
      })),
    );
    render(<FundingEvidence />);
    expect(await screen.findByText("Binance USD-M BTCUSDT perpetual")).toBeInTheDocument();
    expect(screen.getByText(/Funding rate -0.03750000/)).toBeInTheDocument();
    expect(screen.getByText(/2026-10-16T16:00:00Z/)).toBeInTheDocument();
    expect(screen.getByText(/Rate type Regular/)).toBeInTheDocument();
    expect(screen.getByText(LIMITATION)).toBeInTheDocument();
    expect(screen.getByText("Source completeness: COMPLETENESS_UNKNOWN")).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.queryByText(
          /bullish|bearish|crowded long|crowded short|long signal|short signal|regime/i,
        ),
      ).toBeNull();
    });
  });
});
