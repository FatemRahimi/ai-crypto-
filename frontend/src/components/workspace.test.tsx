import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AccountBoard } from "@/components/account/AccountBoard";
import { OpportunityBoard } from "@/components/opportunities/OpportunityBoard";
import { PerformanceBoard } from "@/components/performance/PerformanceBoard";
import { ResearchBoard } from "@/components/research/ResearchBoard";

describe("workspace shells", () => {
  it("does not ask for exchange credentials", () => {
    render(<AccountBoard />);
    expect(screen.getByText(/does not hold funds/i)).toBeInTheDocument();
    expect(screen.getByText(/will never be requested/i)).toBeInTheDocument();
    expect(document.querySelector("input")).toBeNull();
  });

  it("shows opportunity states without a probability", () => {
    render(<OpportunityBoard />);
    expect(screen.getByText("LONG")).toBeInTheDocument();
    expect(screen.getByText("NO TRADE")).toBeInTheDocument();
    expect(screen.getByText(/does not assign probabilities/i)).toBeInTheDocument();
    expect(screen.getByText(/not an opportunity/i)).toBeInTheDocument();
  });

  it("refuses to invent performance", () => {
    render(<PerformanceBoard />);
    expect(screen.getByText(/No performance has been calculated/i)).toBeInTheDocument();
    expect(screen.getAllByText(/No verified history/).length).toBeGreaterThan(0);
  });

  it("keeps research sections closed until opened", () => {
    render(<ResearchBoard />);
    const technical = screen.getByText("Technical").closest("details");
    expect(technical).not.toBeNull();
    expect(technical).not.toHaveAttribute("open");
    expect(screen.getAllByText("No evidence connected.").length).toBeGreaterThan(0);
  });
});
