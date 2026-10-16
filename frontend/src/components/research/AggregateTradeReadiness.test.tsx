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
        json: async () => ({
          canonical_symbol: "BTC/USDT",
          empty: true,
          stored_count: 0,
          window: null,
        }),
      }),
    );
    render(<AggregateTradeReadiness />);
    expect(
      screen.getByText("No aggregate trades are stored. That is not proof the market was idle."),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByText("No aggregate trades are stored. That is not proof the market was idle."),
      ).toBeInTheDocument();
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
    expect(
      await screen.findByText(
        "Stored observations available; clock-window completeness is not proven.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/complete dataset|no missing trades|POC|VAH|VAL|delta|CVD/i)).toBeNull();
  });
});
