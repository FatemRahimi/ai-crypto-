export const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/strategy", label: "Strategy" },
  { href: "/opportunities", label: "Opportunities" },
  { href: "/positions", label: "Positions" },
  { href: "/research", label: "Research" },
  { href: "/performance", label: "Performance" },
  { href: "/account", label: "Account" },
] as const;

export const MARKET_STATES = ["LONG", "SHORT", "WAIT", "NO TRADE"] as const;

export const POSITION_ACTIONS = ["HOLD", "REDUCE", "PARTIAL EXIT", "EXIT", "PROTECT"] as const;
