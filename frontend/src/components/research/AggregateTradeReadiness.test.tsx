import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AggregateTradeReadiness } from "@/components/research/AggregateTradeReadiness";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AggregateTradeReadiness", () => {
  it("says there is no verified window when nothing is stored", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ canonical_symbol: "BTC/USDT", empty: true, stored_count: 0, window: null }),
      }),
    );
    render(<AggregateTradeReadiness />);
    expect(screen.getByText("No verified aggregate trade window")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("No verified aggregate trade window")).toBeInTheDocument();
    });
    expect(screen.queryByText(/POC|VAH|VAL|HVN|LVN/)).toBeNull();
  });

  it("reports stored aggregate trades without a profile measurement", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          canonical_symbol: "BTC/USDT",
          empty: false,
          stored_count: 2,
          window: { completeness: "COMPLETENESS_UNKNOWN" },
        }),
      }),
    );
    render(<AggregateTradeReadiness />);
    expect(await screen.findByText("Aggregate trade data available")).toBeInTheDocument();
    expect(screen.queryByText(/POC|VAH|VAL|delta|CVD/)).toBeNull();
  });
});
