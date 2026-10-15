import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CommandCenter } from "@/components/home/CommandCenter";

describe("CommandCenter", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: "ok",
          service: "ai-crypto-api",
          environment: "test",
          phase: 1,
        }),
      }),
    );
  });

  it("answers from the phase 1 state and labels sample panels as demo", async () => {
    render(<CommandCenter />);
    expect(screen.getByText("No verified market data")).toBeInTheDocument();
    expect(screen.getAllByText("Not evaluated").length).toBeGreaterThan(0);
    expect(screen.getByText("Nothing in this build")).toBeInTheDocument();
    expect(screen.getByText("Demonstration layout")).toBeInTheDocument();
    expect(screen.getAllByText("Demo").length).toBeGreaterThan(0);
    expect(screen.getByText("Sample session")).toBeInTheDocument();
    expect(screen.getByText(/not a price history/i)).toBeInTheDocument();
    expect(screen.getByText(/will not invent market commentary/i)).toBeInTheDocument();
    expect(await screen.findByText(/Reachable \(test\)/)).toBeInTheDocument();
  });
});
