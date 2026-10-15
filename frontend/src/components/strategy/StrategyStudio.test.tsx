import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { StrategyStudio } from "@/components/strategy/StrategyStudio";

describe("StrategyStudio", () => {
  it("keeps intent on the page and leaves approval disabled", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<StrategyStudio />);

    await user.type(screen.getByLabelText("Capital context"), "A future capital note");
    await user.click(screen.getByRole("button", { name: "Keep intent on this page" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent(
      /not sent, saved, compiled, or validated/i,
    );
    expect(screen.getByRole("button", { name: "Approve strategy" })).toBeDisabled();
    expect(screen.getByText("Not run")).toBeInTheDocument();
  });
});
