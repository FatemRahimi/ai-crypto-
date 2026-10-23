# AI Crypto — Project State

Operational handoff for a new ChatGPT or Cursor session. This is not a product pitch.

The checkpoint below was verified when this file was added. It is not a permanent expected `HEAD`.

## 1. Resume Instructions

Before proposing or modifying anything:

1. Verify `main` and `origin/main`.
2. Read `docs/PROJECT_STATE.md`.
3. Read `docs/ROADMAP.md`.
4. Read `docs/DECISION_LOG.md` if it is present.
5. Inspect the relevant code for the requested next phase.
6. Never assume this document overrides newer code.
7. If the SHA or the implementation differs from this file, re-audit before implementation.

Repository: `FatemRahimi/ai-crypto-`

Current verified main at creation of this file:

`98f8c65235385028c20ef05d449637b9b0af8944`

That SHA is the merge commit `merge: phase 3d perpetual funding evidence`. After `main` moves, treat it as history.

This file does not authorize a phase. A sentence here is not an approval to implement it.

### Documents that lag the code

These files still describe an earlier repository. Where they disagree with the code at the checkpoint above, the code wins. Do not "reconcile" them by deleting later evidence from your understanding of the system.

| Document | Conflict with the checkpoint |
| --- | --- |
| `README.md` | Still calls the repository a Phase 1 foundation. It says Phase 1 does not display live market data. The home page can show a stored spot latest price. That price is not a live feed. The Alembic paragraph stops at the technical-evidence table. |
| `docs/ARCHITECTURE.md` | The domain table still says market data is spot-only and describes market intelligence as Phase 3A only. The route table and the persistence paragraph stop before aggregate trades, observed volume, and funding. It also says there is no business logic behind the domain packages, and that the home answers include "no verified market data." Both of those sentences are stale. `backend/app/domains/market_data/__init__.py` already names spot plus USD-M funding. |
| `docs/DATA_ARCHITECTURE.md` | The Phase 2 portion matches the spot candle, trade, and book path. The document stops at Phase 3A and says derivatives are not implemented. Funding, aggregate trades, and observed volume exist. |
| `docs/UI_UX.md` | Home question 1 is still "No verified market data." It also says every research group says that no evidence is connected. The home page can show a stored spot price. Technical, observed-volume, and funding panels now read stored APIs. |
| `docs/QUANT_ARCHITECTURE.md` | The "Phase 1 limit" says no statistic is computed. That is true of the quant domain. It is not true of the evidence calculators. |
| `docs/ROADMAP.md` | The original Phase 2 goal said perpetual observations. What shipped was spot. A short verified-delivery note was added in the continuity commit. The rest of the roadmap was left in place. |
| `backend/app/core/constitution.py` | `PHASE` is still the literal `1`. That is the platform flag, not the product roadmap cursor. |
| `backend/app/domains/market_intelligence/__init__.py` | The phase note mentions 3A and 3C, then says derivatives are absent. Funding lives under `market_data`, not under this package. |
| `frontend/src/components/research/ResearchBoard.tsx` | The page summary still says the other sections have no data source. The Market Profile and Derivatives sections read stored aggregate-trade, observed-volume, and funding APIs. Order flow, fundamental, and quant still say no evidence is connected. |
| `frontend/src/components/home/ChartWorkspace.tsx` | The frame says "No feed" and "No verified series." Stored candles can exist. This frame does not plot them. |

`docs/PROJECT_CONSTITUTION.md` and `docs/SECURITY.md` still match the security invariants. `docs/DECISION_LOG.md` D001–D018 were already on this checkpoint. D006's sentence that research uses empty states is the Phase 1 decision. The research page now reads stored evidence for the families in section 6. D017's line that derivatives stay unimplemented is the Phase 3A record. D023 later records funding only.

## 2. Product Definition

Personal Adaptive AI-Quant BTC Futures Trading Intelligence, Strategy, Risk, Capital Management, and eventually Controlled Execution Platform.

It is not merely an indicator dashboard, a TradingView clone, a generic crypto bot, a ChatGPT wrapper, a signal generator, or a custodial wallet.

Long-term decision chain:

Market Data → Evidence → BTC Behaviour / Regime → Quant Validation → Strategy → Opportunity → Risk & Capital → AI Synthesis → Decision → Position Intelligence → Controlled Execution → Performance / Learning

### Vision versus current implementation

The chain above is the product direction. Only the first evidence steps exist, and only in the narrow form in section 6.

Implemented today: a modular monolith, a refusing execution boundary, public spot BTC/USDT observations, deterministic technical evidence from those candles, spot aggregate trades, exact-price observed volume, and public USD-M BTCUSDT funding history.

Not implemented: regime classification, quant validation runs, strategy compilation, opportunities, risk rules, capital and leverage, AI synthesis, position intelligence, exchange connectivity, paper or testnet trading, and live execution.

`NO TRADE` is a valid future decision. The proposal contract already includes `no_trade` and `wait`. Neither can be authorized for execution.

## 3. Core Principles

`docs/PROJECT_CONSTITUTION.md` and `backend/app/core/constitution.py` state: No evidence → no claim. `authorize_execution` raises that sentence when evidence is missing. It authorizes only `long` or `short`, and only when quant status is `passed`. `wait` and `no_trade` cannot become an execution intent.

The extended chain below is the product rule. Only the first link and the authorization choke point exist in code. There is no quant runner that implements "validated edge":

No Evidence → No Claim → No Validated Edge → No Trade.

FACT ≠ MODEL OUTPUT ≠ AI RECOMMENDATION.

AI must not invent support levels, probabilities, backtest results, returns, or market measurements.

A numeric market claim has to come from a verified observation or a deterministic calculator over stored inputs. A probability, expectancy, or backtest result would later have to come from a validated quantitative run. No such run exists.

A language-model sentence is not evidence. An evidence source of `llm`, `model`, `ai`, `guess`, or `opinion` is rejected.

`NO TRADE` is a valid future output. Absence of a number is reported as absence. It is not filled with zero or with a sample.

## 4. Security / Execution Invariants

Verified in `backend/app/core/constitution.py` at this checkpoint:

- `execution_enabled = false` (`EXECUTION_ENABLED: Literal[False] = False`)
- `custody = none`
- `WITHDRAWAL_PERMISSION_ALLOWED = False`
- sessions, MFA, passkeys, rate limiting, audit log, and encrypted exchange credentials are `not_implemented`

There is no live execution, no order route, no position book, no withdrawal, no custodial wallet, no copy trading, and no autonomous execution loop.

`ExecutionGateway.submit` raises `ExecutionDisabledError`. `RiskEngine` raises `RiskEngineNotEnabled`. `authorize_execution` can build an `ExecutionIntent` only when evidence, quant, risk, and policy all pass, and the kill-switch flag is off. The gateway still refuses that token. Building a token is not submission. The AI package must not import the gateway or call `authorize_execution`.

CORS allows GET and OPTIONS only. Credentials are disabled.

Long-term controlled execution, if it is ever approved, stays behind the roadmap gates: evidence, quant validation, risk controls, the identity gate, read-only exchange integration, paper trading, testnet, limited live validation, and deterministic execution gates. An operator kill switch is planned and does not exist. AI may never override hard risk limits. None of those later gates is started.

## 5. Verified Phase Status

Status below is from merges on this checkpoint, migrations, and the modules those merges added. It is not taken from a prompt.

`constitution.PHASE` remains `1`. Do not read that flag as "product Phase 3 has not shipped" or as "the product is still only Phase 1."

| Phase | Status | Evidence |
| --- | --- | --- |
| Phase 1 — Foundation | CLOSED | Initial commit `390806f8dcaa656faaa33ab2b3c1e211a744d384`. Modular monolith, proposal choke point, refusing risk engine, refusing gateway, Alembic `20261014_0001` with no business tables, application shell. |
| Phase 1.5 — Foundation hardening | CLOSED | D011–D015 and `docs/SECURITY.md` ("Phase 1.5 dependency decisions"). Local database path, ports, and the decision not to force dependency upgrades. No dedicated Phase 1.5 merge commit was found. |
| Phase 2 — Spot BTC/USDT market data | CLOSED | Merge `f30c4cbb4565857f463b6094d036cfbb8574f857`. Migration `20261015_0002`. D016. The original roadmap sentence said perpetual. The code stores spot. |
| Phase 3A — Deterministic technical evidence | CLOSED | Merge `649ac5227276e782e759670615d3faf5a0f2e9c7`. Migrations `20261016_0003` and fingerprint `20261016_0004`. D017, D018. |
| Phase 3B — BTC aggregate-trade foundation | CLOSED | Feature commit `d67d4dce606f6c648e7bf0054aa48783f8ecc812`, then completeness semantic fix merge `b4903c5f72c3d0a327ab6a7ae6411e59fc5e434c`. Migration `20261016_0005`. Completeness of a clock window is not claimed. |
| Phase 3C — Observed volume at price / observed POC | CLOSED | Merge `cd716281f35457159c1fb36e250b2cb559cf67d7`. Migration `20261016_0006`. |
| Phase 3D — Public BTCUSDT USD-M perpetual funding | CLOSED | Merge `98f8c65235385028c20ef05d449637b9b0af8944`. Second parent `35fbf178560fe08f08e7e8b2054c0c05f92c605e`. Migration `20261017_0007`. |

Phase 3 as a whole is not closed. Market profile, order flow, and derivatives other than funding are not closed.

Phase 3E does not exist in this repository. Do not invent it.

Repository Alembic head is `20261017_0007`. Chain: `20261014_0001` → `20261015_0002` → `20261016_0003` → `20261016_0004` → `20261016_0005` → `20261016_0006` → `20261017_0007`.

Later roadmap phases 4 through 13, and the identity gate before any exchange connection, are not started. The packages for those later phases are `planned`, except `risk` and `execution`, which are `disabled`. The `ai` package is `foundation` only as far as constructing a `TradeProposal`. No model is connected. That is not Phase 9.

## 6. Current Evidence Inventory

Ingestion is a manual command. There is no background worker and no POST ingest API. Read routes serve stored rows. They do not call Binance during the request, and they do not run a calculator.

### Spot — `BTC/USDT`

Identity: provider `binance_spot`, market type `spot`, provider symbol `BTCUSDT`, canonical symbol `BTC/USDT`. Public host `https://data-api.binance.vision`. No account credentials.

| Family | What exists | Limitation |
| --- | --- | --- |
| Candles | Closed klines for `1m`, `5m`, `15m`, `1h`, `4h`, `1d`. UTC. `numeric(38, 18)`. Invalid OHLC and open candles are rejected. | Gaps are detected and are not filled. `STALE` is computed on read. This is not a perpetual candle. |
| Recent trades and book ticker | Optional stored rows from the Phase 2 ingest command (`market_trades`, `market_book_snapshots`). | The read API does not call the provider. Book ticker has no provider source timestamp. `buyer_is_maker` is not a buy or sell signal. The public trade websocket is not connected. D016 records continuous streaming as Phase 2.1. That stream is not implemented, and naming it is not an approval to build it next. |
| Aggregate trades | `GET /api/v3/aggTrades` stored in `market_aggregate_trades`, separate from ordinary trades. Read routes: `GET /api/v1/market-data/aggregate-trades` and `GET /api/v1/market-data/aggregate-trade-windows`. | `CompletenessStatus` still names `COMPLETE` and `GAP_DETECTED`. `assess_aggregate_completeness` does not return either. A successful retrieval stays `COMPLETENESS_UNKNOWN`, including a retrieval that stops on the row cap. An aggregate-id discontinuity is recorded and is not filled. An empty response is not proof the market was idle. Binance ids are not treated as a gap-free clock-window ledger. |
| Swing structure | Confirmed strict pivots and higher/lower/equal labels, calculator `technical-evidence-v1`. | A pivot is not emitted until the later candles exist. Labels are not orders. A candle gap yields `GAP_DETECTED` and no filled measurement. |
| Support / resistance | Exact prices of confirmed pivot highs and lows. `touch_count` counts pivots at that exact price. | Not a strength score, not a zone, not supply/demand, not Fibonacci. |
| Range statistics | Max high, min low, range, midpoint, and range as a percentage of the low. | Not a volatility regime and not a forecast. |
| Candle VWAP | Volume-weighted `(high + low + close) / 3` using candle base volume. Result limitation `candle_proxy_not_trade_vwap`. | This is not trade VWAP. Zero total volume stores no VWAP. |
| Observed volume at price | Exact-price buckets of stored aggregate base quantity. Calculator `observed-volume-at-price-v1`. CLI `python -m app.domains.market_intelligence.observed_volume`. Read API `GET /api/v1/observed-volume` does not calculate. | Not a market profile, not a value area, not VAH/VAL, not HVN/LVN. `buyer_is_maker` is not bid or ask size and is not summed. A calculation that reaches the stored-row cap does not produce a profile. |
| Observed POC | The exact stored price with the greatest summed base quantity. Ties break to the lower price (`poc_tie` is recorded). | Not a session POC and not a complete-market POC. Complete clock-window coverage is not proven. There is no session calendar. |

Technical evidence read routes are `GET /api/v1/technical-evidence` and `GET /api/v1/technical-evidence/latest`. Calculation is `python -m app.domains.market_intelligence` and uses candles already stored.

Same calculator version, parameters, and input fingerprint do not insert a second technical row. A conflicting payload keeps the stored row. A changed candle changes the fingerprint and inserts a new row.

### Perpetual — `BTCUSDT-PERP`

Identity: provider `binance_usdm`, market type `perpetual`, provider symbol `BTCUSDT`, canonical symbol `BTCUSDT-PERP`. The provider symbol text matches spot. The market does not.

| Family | What exists | Limitation |
| --- | --- | --- |
| Historical funding | Public `GET /fapi/v1/fundingRate` on `https://fapi.binance.com`. Rows in `market_funding_observations`. Windows in `market_funding_windows`. Rate types `Regular` and `Special`. CLI `python -m app.domains.market_data.funding_cli`. Read API `GET /api/v1/funding?symbol=BTCUSDT-PERP`. | Ingest refuses to write unless exchange info confirms `contractType=PERPETUAL`. `markPrice` is not persisted. Cadence is not hard-coded. Spacing is not a gap. A missing timestamp is not inserted. An empty provider window stores no zero rate. Successful coverage stays `COMPLETENESS_UNKNOWN`. A retrieval that stops on the row cap (default 1000, hard maximum 5000) stays `COMPLETENESS_UNKNOWN`. It is not an exhaustive archive. The window check constraint allows only `COMPLETENESS_UNKNOWN`, `EMPTY`, and `INVALID`. The rate is not a long, short, crowded, bullish, or bearish claim. |

Spot candles, spot trades, and observed volume must not be described as perpetual. Funding must not be described as a spot print.

## 7. Known Missing Evidence

Checked against modules, migrations, and the research page. These are absent:

- open interest
- basis
- mark and index series (the funding adapter does not persist `markPrice`)
- liquidations
- realized-volatility regime
- joint multi-timeframe state
- delta, CVD, and footprint
- absorption and imbalance
- value area, VAH/VAL, HVN/LVN, single prints, and any other full market profile
- session calendar
- macro, news, ETF, and other event evidence
- perpetual candles, perpetual trades, and a perpetual order book
- a connected public trade stream
- regime labels
- backtests, probabilities, and expectancy

The research page states that open interest, liquidations, and basis are not connected, and that supply, demand, liquidity, and Fibonacci are not calculated. Order flow, fundamental, and quant research groups still render "No evidence connected."

Do not promote an item on this list into the next phase because it is listed.

## 8. Phase 3 Evidence Boundary

Phase 3 stores deterministic evidence. Evidence is not automatically an edge, a strategy, a signal, a regime, a probability, or a trade recommendation.

Do not turn funding into SHORT or LONG.

Do not turn an observed POC into a trade signal.

A downstream phase would have to validate any use of these records. The quant domain is still `planned`. No validation run exists to pass.

## 9. Quant Validation Standard

Future standard, not an implemented runner. `backend/app/domains/quant` has no backtest and no probability model. `docs/QUANT_ARCHITECTURE.md` and roadmap Phase 5 are the existing contract for that future runner:

- chronological testing
- out-of-sample testing
- walk-forward where appropriate
- fees
- funding
- slippage
- no leakage
- sample-size reporting
- regime breakdown
- calibration where a probability is used

An indicator or an evidence object is not a validated edge. The UI must not show a backtest except by a stored run id. No run id exists. Failed and insufficient runs would be stored too, once that phase exists.

## 10. AI Boundary

Desired architecture:

RAW DATA → CANONICAL DATA → DETERMINISTIC EVIDENCE → BEHAVIOUR / REGIME FEATURES → QUANT VALIDATION → STRATEGY → OPPORTUNITY → RISK & CAPITAL → AI SYNTHESIS → DECISION → POSITION INTELLIGENCE → CONTROLLED EXECUTION → LEARNING

What exists now is RAW and CANONICAL spot data, a separate perpetual funding series, and DETERMINISTIC EVIDENCE for the families in section 6.

Behaviour, regime, quant validation, strategy, opportunity, risk rules, capital, AI synthesis, position intelligence, controlled execution, and learning are future layers. They are not implemented.

The AI package can construct a `TradeProposal` in code. No model is connected. The copilot textarea is disabled and does not send messages. AI must not go from price plus indicators to BUY or SELL. A proposal is not an order. It has no size, price, leverage, or credential.

## 11. UI / UX Direction

Intended navigation, and the routes that exist today:

| Route | Label | What the page actually does |
| --- | --- | --- |
| `/` | Home | Command center. The first answer can show a stored spot `BTC/USDT` latest price with source and freshness, or an explicit empty or unavailable state. The other command answers are still the unevaluated Phase 1 copy. Demo panels stay marked Demo. The chart frame is an empty SVG. It says no feed and does not plot stored candles. The copilot is disabled. |
| `/strategy` | Strategy | Intent form kept on the page. It does not call the network. Approve is disabled. Quant status is not run. |
| `/opportunities` | Opportunities | State vocabulary and an empty sample card. No probabilities. |
| `/positions` | Positions | Field list and disabled actions: hold, reduce, partial exit, exit, protect. No position book. |
| `/research` | Research | Technical evidence, aggregate-trade readiness, observed volume, and funding read stored APIs when rows exist. The page summary still says the other sections have no data source. That sentence is stale for those panels. Order flow, fundamental, and quant still say no evidence is connected. The "Market Profile" heading is a section title. The panel under it is observed volume, not a market profile. |
| `/performance` | Performance | Empty sections. No sample equity curve. |
| `/account` | Account | States that the platform holds no funds and has no exchange connection. Security, sessions, and audit are marked planned. No credential field. |

The shell subtitle still says "Phase 1 foundation." That label is stale relative to section 5. The pages above are the actual surface.

Confidence is not probability. Do not show a numerical probability unless a validated quantitative model produced it. No such model exists.

AI is not a giant central chat box. The copilot stays a disabled side panel.

Evidence should stay drillable when a later decision exists: Decision → Reasoning → Evidence → Raw / Provenance. Today the research panels show stored evidence and its limitation text. They do not sit under a decision.

## 12. Git / Engineering Workflow

Required path:

main clean → new phase or fix branch → implementation → tests → PASS → commit → push the feature branch → independent GitHub or code review → merge approval → controlled merge to main → post-merge verification

Never push implementation directly to `main`.

Never merge because Cursor reports PASS. Current code and repository evidence have to be checked independently. A green local run is not merge approval.

Controlled merges of the closed phases on this checkpoint used `--no-ff` merge commits. That history is the record. It is not a license to merge the next branch.

Do not delete a feature branch unless the operator asks.

## 13. Decision Protocol

Use this order before an implementation phase:

TRUTH → EVIDENCE → CODEBASE VERIFY → ASSUMPTIONS → RED TEAM → COUNTER-ARGUMENT → TRADE-OFF → BEST OPTION → REGRESSION TEST → ACCEPTANCE GATE → CONFIDENCE

If the evidence is insufficient: NOT VERIFIED.

If the acceptance gate fails: FIX REQUIRED.

Do not advance a phase until its gate passes. Do not treat a documentation file as the gate.

## 14. Cursor Model Selection

Guidance for Cursor sessions on this repository. It is not a correctness guarantee.

AUTO is for deterministic, low-risk, mechanical work:

- Git verification
- a controlled merge that has already been specified
- test, lint, and build execution
- a simple, narrowly specified edit

GROK is for reasoning-heavy work:

- a new phase implementation
- multi-file code reasoning
- architecture
- debugging
- database, service, and API integration
- edge-case analysis
- red-team review

For a mixed task, say which model is for which portion. Checking out a branch and running tests can be AUTO. Deciding what the next evidence family should be is GROK.

## 15. Current Decision Point

Phase 3D is closed on the checkpoint in section 1.

The next product phase has not been approved.

Before any Phase 3E or Phase 4 implementation, perform a fresh evidence-gap and roadmap decision against the actual post-3D code. Do not start from this file alone.

Candidate future evidence families include open interest, basis, realized volatility, and other derivatives evidence. None of them is approved because it appears in this sentence.

The next step after the documentation task that added this file is a read-only post-3D roadmap and evidence-gap review.

Do not implement that review's candidates inside the documentation task.

## 16. Resume Prompt

Copy this into a new ChatGPT session:

```text
I am continuing the ai-crypto project in
FatemRahimi/ai-crypto-.

Treat GitHub as the source of truth.

Read:
docs/PROJECT_STATE.md
docs/ROADMAP.md
docs/DECISION_LOG.md

Verify current main/origin state and relevant code.

Do not modify anything yet.

Tell me:
1. current verified project state,
2. last closed phase,
3. current evidence inventory,
4. unresolved risks/gaps,
5. next approved action.

Apply the decision and engineering protocols from PROJECT_STATE.md.

If repository state differs from the recorded checkpoint,
re-audit rather than guessing.
```
