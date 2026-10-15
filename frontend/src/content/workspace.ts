export const RESEARCH_SECTIONS = [
  {
    id: "technical",
    title: "Technical",
    topics: [
      "Market structure",
      "Support / resistance",
      "Supply / demand",
      "Liquidity",
      "Fibonacci",
    ],
  },
  {
    id: "profile",
    title: "Market Profile",
    topics: ["Single prints", "POC", "VAH / VAL", "HVN / LVN"],
  },
  {
    id: "flow",
    title: "Order Flow",
    topics: ["Delta", "CVD", "Footprint", "Absorption", "Imbalances"],
  },
  {
    id: "derivatives",
    title: "Derivatives",
    topics: ["Open interest", "Funding", "Liquidations", "Basis"],
  },
  {
    id: "fundamental",
    title: "Fundamental",
    topics: ["Macro", "News", "ETF context", "Global markets"],
  },
  {
    id: "quant",
    title: "Quant Evidence",
    topics: ["Historical analogues", "Regime", "Backtest results"],
  },
] as const;

export const OPPORTUNITY_FIELDS = [
  "Entry zone",
  "Invalidation",
  "Stop",
  "Targets",
  "Evidence",
  "Quant status",
  "Risk status",
  "Strategy match",
] as const;

export const POSITION_FIELDS = [
  "Entry",
  "Current price",
  "PnL",
  "Stop",
  "Targets",
  "Liquidation",
  "Thesis health",
  "Risk health",
  "AI recommendation",
] as const;

export const PERFORMANCE_SECTIONS = [
  "P&L",
  "Drawdown",
  "Strategy performance",
  "Trade history",
  "Risk performance",
  "Weekly / monthly performance",
  "Trading DNA",
] as const;

export const ACCOUNT_SECTIONS = [
  {
    title: "Account & Capital",
    body: "This platform does not hold funds. Future balances would come from an exchange, and none is connected. No balance is shown because none can be verified.",
    planned: false,
  },
  {
    title: "Exchange Connections",
    body: "No connection form is available. Exchange API secrets are not requested, and they will not be stored in the browser, local storage, or git.",
    planned: false,
  },
  {
    title: "Security",
    body: "Sign-in is not available. MFA, passkeys, and secure sessions are planned. They are not active in this build.",
    planned: true,
  },
  {
    title: "Notifications",
    body: "No notification channel is connected.",
    planned: true,
  },
  {
    title: "Trading Permissions",
    body: "Order placement is disabled. An operator kill switch is planned and is not available, because there is no live trading to stop. Withdrawal permission will never be requested.",
    planned: true,
  },
  {
    title: "Sessions / Devices",
    body: "No sessions exist. Device tracking is not implemented.",
    planned: true,
  },
  {
    title: "Audit History",
    body: "No audit history exists. The audit log is not implemented.",
    planned: true,
  },
] as const;
