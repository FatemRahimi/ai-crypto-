import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ObservedVolume } from "@/components/research/ObservedVolume";

const LIMITATION =
  "Based on stored aggregate-trade observations. Complete clock-window coverage is not proven.";

afterEach(() => {
  vi.unstubAllGlobals();
});

function evidencePage() {
  return {
    canonical_symbol: "BTC/USDT",
    empty: false,
    detail: "Stored observed volume-at-price evidence.",
    execution_enabled: false,
    records: [
      {
        sufficiency: "OBSERVED",
        source_limitation: LIMITATION,
        source_completeness: "COMPLETENESS_UNKNOWN",
        observed_poc_price: "10.5",
        poc_tie_count: 2,
        poc_tie: true,
        largest_aggregate_base_quantity: "1.5",
        derived_largest_aggregate_share_of_observed_base_volume: "0.5",
        buckets: [
          { price: "10.5", observed_base_volume: "2", aggregate_count: 2 },
          { price: "11", observed_base_volume: "2", aggregate_count: 1 },
        ],
      },
    ],
  };
}

describe("ObservedVolume", () => {
  it("says no evidence was calculated when nothing is stored", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ empty: true, records: [] }),
      }),
    );
    render(<ObservedVolume />);
    expect(
      screen.getByText("No observed volume-at-price evidence has been calculated or stored."),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByText("No observed volume-at-price evidence has been calculated or stored."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/no volume existed|no POC existed|market had no activity/i)).toBeNull();
  });

  it("renders the stored observed measurement and its limitation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => evidencePage(),
      }),
    );
    render(<ObservedVolume />);
    expect(await screen.findByText("Observed Volume at Price")).toBeInTheDocument();
    expect(screen.getByText("Observed Point of Control 10.5")).toBeInTheDocument();
    expect(screen.getByText(LIMITATION)).toBeInTheDocument();
    expect(screen.getByText("Source completeness: COMPLETENESS_UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText(/Tied observed point-of-control buckets: 2/)).toBeInTheDocument();
    expect(screen.getByText("10.5 observed base volume 2")).toBeInTheDocument();
  });

  it("does not render value area, order flow, or a complete profile claim", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => evidencePage(),
      }),
    );
    render(<ObservedVolume />);
    await screen.findByText("Observed Volume at Price");
    expect(screen.queryByText(/VAH|VAL|HVN|LVN|TPO/)).toBeNull();
    expect(screen.queryByText(/Delta|CVD|Footprint/)).toBeNull();
    expect(screen.queryByText(/LONG|SHORT|probability|signal/i)).toBeNull();
    expect(
      screen.queryByText(/complete volume profile|complete market profile|market POC/i),
    ).toBeNull();
  });
});
