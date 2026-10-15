import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SideNav } from "@/components/shell/SideNav";
import { NAV_ITEMS } from "@/content/navigation";

vi.mock("next/navigation", () => ({
  usePathname: () => "/strategy",
}));

describe("SideNav", () => {
  it("lists the primary destinations and marks the current page", () => {
    render(<SideNav />);
    for (const item of NAV_ITEMS) {
      expect(screen.getByRole("link", { name: item.label })).toHaveAttribute("href", item.href);
    }
    expect(screen.getByRole("link", { name: "Strategy" })).toHaveAttribute("aria-current", "page");
  });
});
