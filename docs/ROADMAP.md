# Roadmap

Phases ship only when their exit criteria are true in the running system. A screen that needs a number waits for the phase that can produce that number.

Sequencing notes, where the original order needed a gate:

- An evidence store is part of Phase 2, not a later retrofit. Later phases cite those records.
- Identity, sessions, MFA, and audit logging are a hard gate before any exchange connection. They are not a substitute for Phase 2. Recommended placement: after Phase 1 approval, in parallel with early market-data work, finished before Phase 11.
- Phase 5 is a gate for any probability, expectancy, or backtest shown in the interface.
- Phase 8 is a gate for any size, leverage, or free-collateral figure.
- An operator-facing kill switch, separate from the Phase 1 model invariant, is a gate for Phase 12 and Phase 13.
- Phase 13 does not start because Phase 12 exists. It starts after paper/testnet evidence and an explicit approval.

## Phase 1 — Foundation

Status: this repository.

Delivered: modular monolith, domain boundaries, proposal and execution choke point, refusing risk engine, refusing gateway, PostgreSQL and Alembic toolchain, security baseline, application shell, constitution.

Exit: tests, type checks, and the production build pass. No order can be submitted.

## Phase 2 — Market data layer

Status: closed. Merge `f30c4cbb4565857f463b6094d036cfbb8574f857`.

Goal, as originally written: verified BTC perpetual observations with source, symbol, timestamp, and granularity.

What shipped: public spot BTC/USDT only (`BTC/USDT`, provider `binance_spot`). Perpetual candles were not stored. USD-M perpetual funding is the closed Phase 3D slice and uses a separate identity, `BTCUSDT-PERP`. See D016 and D019.

Deliver:

- A single ingestion boundary in `market_data`
- Raw storage separated from derived series
- Health of the feed that is distinct from application health
- Gap detection
- No synthetic fills for missing candles
- API and UI that show "no data" when the feed is down, including the last verified timestamp when one exists

Exit: a local replay or a public market-data source can be queried, and every served price cites its source. Still no orders.

## Phase 3 — Technical, profile, and derivatives evidence

Status: the phase is not closed. The slices below are closed on main. No Phase 3E is defined or approved.

Goal: deterministic evidence objects for structure, market profile, order flow, and derivatives.

Closed slices:

- 3A — deterministic technical evidence from verified spot candles. Merge `649ac5227276e782e759670615d3faf5a0f2e9c7`.
- 3B — spot aggregate-trade storage. Clock-window completeness is not claimed. Completeness semantic fix merge `b4903c5f72c3d0a327ab6a7ae6411e59fc5e434c`.
- 3C — observed volume at exact price and an observed POC from stored aggregate trades. Merge `cd716281f35457159c1fb36e250b2cb559cf67d7`.
- 3D — public BTCUSDT USD-M perpetual funding observations. Merge `98f8c65235385028c20ef05d449637b9b0af8944`.

Market profile value area, order flow, open interest, basis, liquidations, and the rest of this phase goal are not implemented. Naming them here does not approve a next slice.

Phase 3A is the technical slice only. It calculates structure, support and resistance, range statistics, and candle-proxy VWAP from verified candles. Market profile, order flow, and derivatives were not part of 3A. Funding, added later in 3D, is funding history only. It is not a directional derivative signal.

Deliver: named calculators whose inputs are Phase 2 records. Each output stores inputs, parameters, and code version. The research page opens a section only when that section has records.

Exit: a BTC view can show support, profile nodes, or funding only when the calculator produced them. No LLM commentary is stored as a measurement.

## Phase 4 — Strategy engine and compiler

Goal: turn an operator's stated intent into measurable rules.

Deliver: persisted strategy drafts, a compiler from structured intent to rules, versioning, and an inactive state. Desired return is stored as a preference and is never displayed as expectancy.

Exit: a strategy can be saved and diffed. It cannot be approved, and it cannot size or place an order.

## Phase 5 — Quant research and backtesting

Goal: a reproducible research runner.

Deliver: dataset snapshots, cost and funding assumptions, walk-forward or equivalent out-of-sample separation, and a run record that the performance and strategy screens can cite. Failed and insufficient runs are stored too.

Exit: the UI can show a backtest only by run id. There is no hand-entered result.

## Phase 6 — Regime and adaptive BTC behaviour

Goal: classify BTC behaviour from Phase 3 and Phase 5 features.

Deliver: a regime model with a feature list, a training or calibration record, and a refusal when features are missing. Labels are measurements from that model, not chat output.

Exit: the command center can say which regime is current only while the feature timestamp is inside a defined freshness window.

## Phase 7 — Opportunity engine

Goal: assemble LONG, SHORT, WAIT, or NO TRADE candidates.

Deliver: entry zone, invalidation, stop, targets, evidence ids, quant status, risk status, and strategy match. WAIT and NO TRADE are successful outputs. A candidate has no probability field unless Phase 5 attached a model run.

Exit: every directional card fails to render if evidence or invalidation is missing.

## Phase 8 — Risk, capital, and leverage

Goal: deterministic limits on exposure, loss, and leverage.

Deliver: pure functions over verified account state and strategy constraints. The risk package remains free of model calls. Missing equity or missing mark price rejects the decision. Capital stays an exchange concept; this phase does not move funds.

Exit: the disabled risk engine is replaced by rules covered by tests, and an AI proposal still cannot set `decided_by`.

## Phase 9 — AI intelligence and copilot

Goal: a copilot that drafts proposals and explains evidence that already exists.

Deliver: tool use limited to read models and `draft_trade_proposal`. Prompts cannot add an evidence source of `llm`. The copilot UI stays disabled until this phase. Explanations quote evidence ids.

Exit: the import boundary test still fails the build if AI code reaches the gateway.

## Phase 10 — Position intelligence and notifications

Goal: monitor a verified position and notify on real state changes.

Deliver: thesis health and risk health from rules, notification outbox, and deduplicated alerts. Actions remain recommendations: hold, reduce, partial exit, exit, protect. None of them submit.

Exit: a notification payload is rejected when it contains a number that is not in the position or evidence store.

## Identity gate — before any exchange connection

Goal: know which human is operating the system.

Deliver: sessions, MFA or passkeys, device list, server-side secret handling, rate limiting, brute-force protection, and an append-only audit log. This gate is required before Phase 11 even if the market-data phases are unfinished. It does not authorize trading.

Exit: an unauthenticated client cannot read account data. Audit rows do not contain secrets.

## Phase 11 — Read-only exchange integration

Goal: read balances, positions, and fills from the operator's exchange account.

Deliver: encrypted credential storage, rotation, no withdrawal scope, server-side secrets only, and reconciliation against the local position view. The account page may show a balance only from this read.

Exit: a credential cannot be returned to the browser. The execution gateway still refuses orders.

## Phase 12 — Paper and testnet trading

Goal: exercise the full proposal path against a simulator or a testnet.

Deliver: the gateway gains one adapter, selected by configuration, defaulting to off. The operator kill switch is a real control and fails closed. Fills are tagged paper or testnet so they cannot be mixed into live performance.

Exit: a live credential cannot be used by the paper adapter. AI still cannot call `submit`.

## Phase 13 — Controlled live execution

Goal: place a live order only through the restricted gateway, after every prior gate.

Deliver: explicit arming, size from Phase 8, permissions narrower than the account, idempotency, and an audit record for each decision. No autonomous loop that re-arms itself.

Exit: with the kill switch engaged, submission tests fail closed. A proposal with a skipped quant or risk step never becomes an order.

## Not on this roadmap

Custodial wallets, withdrawal automation, copy trading, and unbounded autonomous execution.
