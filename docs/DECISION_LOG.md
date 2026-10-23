# Decision log

## D001 — Modular monolith

Date: 2026-10-14
Status: accepted

The first years of this system share one database and one API process. Domain packages provide boundaries without network hops. Microservices, Kubernetes, and a message bus are deferred until a measured operational need exists.

## D002 — AI stops at a proposal

Date: 2026-10-14
Status: accepted

The AI package may construct a `TradeProposal`. It may not import the execution gateway or call `authorize_execution`. An execution intent carries no size, price, or secret, and the Phase 1 gateway refuses every intent anyway.

## D003 — Risk fails closed and stays deterministic

Date: 2026-10-14
Status: accepted

There is no temporary risk rule that approves proposals while the real engine is unfinished. `RiskEngineNotEnabled` raises. A risk decision cannot name a language model as its author.

## D004 — No domain tables in Phase 1

Date: 2026-10-14
Status: accepted

Alembic is wired, and the first revision creates no business tables. Empty tables for audit, users, or candles would imply persistence that does not exist. Tables arrive with the feature that writes them.

## D005 — PostgreSQL via Compose, application on the host

Date: 2026-10-14
Status: accepted

Docker Compose is responsible for local PostgreSQL only. The API and the web app run directly on Windows so the edit-reload loop stays simple. The API tolerates a missing database instead of refusing to boot.

Consequence: on a machine without Docker, readiness stays degraded until PostgreSQL is provided another way.

## D006 — Demo copy stays in the frontend

Date: 2026-10-14
Status: accepted

Sample layout text is hardcoded in the web app and marked Demo. The API has no fixture prices. Performance and research screens use empty states rather than illustrative statistics.

## D007 — System fonts

Date: 2026-10-14
Status: accepted

The shell uses the Windows font stack. A webfont download is not required to build or run.

## D008 — Sync SQLAlchemy

Date: 2026-10-14
Status: accepted

The Phase 1 API is synchronous. The workload is health checks and a platform document. Async I/O can be reconsidered when ingestion or exchange I/O is real.

## D009 — Secret key is reserved, not a session

Date: 2026-10-14
Status: accepted

`APP_SECRET_KEY` is required to be strong in production so the setting exists before sessions do. Phase 1 does not create cookies or tokens with it. Documentation and the platform endpoint say sessions are not implemented, so the setting is not mistaken for an active control.

## D010 — Identity is a gate before exchange access

Date: 2026-10-14
Status: accepted

The requested roadmap's Phase 11 reads an exchange account. That read is unsafe without authentication, audit, and server-side credential handling. Those are an inserted gate, not a renumbering of the market-data phases. See `docs/ROADMAP.md`.

## D011 — Isolated local PostgreSQL, without guessing admin access

Date: 2026-10-15
Status: accepted

AI-Crypto uses database `aicrypto` and login role `aicrypto`. The application URL must not be a PostgreSQL superuser.

PostgreSQL 16 is already listening on port 5432 and PostgreSQL 18 on 5433. Both clusters require `scram-sha-256`. This environment had no `pgpass` file and no `PGPASSWORD`, so the role and database were not created and no existing role was altered. The API keeps running with readiness degraded until the operator creates that role with the password stored only in `.env`.

## D012 — Ports are configuration

Date: 2026-10-15
Status: accepted

`API_HOST` and `API_PORT` control `python -m app`. `NEXT_PUBLIC_API_URL` controls the browser. They are separate because the browser must not read the API's private environment. When port 8000 is taken, set `API_PORT=8001` and point `NEXT_PUBLIC_API_URL` at `http://127.0.0.1:8001`. Unrelated listeners are left running.

## D013 — Do not suppress the Cursor hydration overlay

Date: 2026-10-15
Status: accepted

The overlay observed in Cursor's browser was a mismatch on `data-cursor-ref`, an attribute that browser injects. Application components do not branch on `window`, `Date.now()`, or `Math.random()`. `suppressHydrationWarning` is not used. The same home page, loaded by headless Chrome against the dev server, had no `data-cursor-ref` nodes and no hydration console message. Application code was left unchanged.

## D014 — No forced dependency upgrades in Phase 1.5

Date: 2026-10-15
Status: accepted

`npm audit fix --force` was rejected. It would install Vitest 5, downgrade `eslint-config-next` to 14, or install Next.js 16. None of those is a drop-in patch. Critical findings are in the Vitest/tinypool development tree, which is absent from `npm ls --omit=dev`. The production finding is PostCSS nested under Next 15.5.28; this application does not parse untrusted CSS at request time. Those packages stay on the current lines until an upgrade is planned and tested. `pip-audit` 2.10.1 is a development-only Python check. It reported no known vulnerabilities in the installed third-party packages. The unpublished local project was skipped by that tool.

## D015 — Repository `.env` path was already the repository root

Date: 2026-10-15
Status: accepted

`backend/app/core/config.py` resolves `Path(__file__).parents[3]` to the repository root and loads `<root>/.env`. `parents[2]` is the `backend` directory, and `parents[4]` is outside the repository. That index was verified and left unchanged.

The process still failed to start from the local file because `APP_ENV=development` is not one of `local`, `test`, or `production`. Settings refused to build, so Alembic never received `DATABASE_URL` from that file. The local file now uses `APP_ENV=local`. The database password was not changed.

## D016 — Phase 2 public BTC market data

Date: 2026-10-15
Status: accepted

Phase 2 stores spot BTC/USDT only. The provider is Binance's public market-data host, which documents unauthenticated klines, recent trades, and book ticker. No account credentials are added. A provider interface keeps that payload out of the canonical tables.

PostgreSQL remains the store. TimescaleDB, Kafka, and a live socket are not introduced. The public trade stream is recorded as Phase 2.1. Timestamps are UTC. Persisted prices and quantities are decimals. Invalid observations are rejected. Missing candles are reported as gaps and are not fabricated. Read endpoints return stored rows only, including an explicit empty state when nothing verified is on file. Execution stays disabled and custody stays none.

## D017 — Phase 3A is deterministic technical evidence

Date: 2026-10-16
Status: accepted

Technical evidence is calculated only from verified Phase 2 candles and stored in `technical_evidence`, not on the candle rows. The first calculators are strict confirmed pivots, structure labels, exact pivot support and resistance, range statistics, and a candle-proxy VWAP. A pivot waits for its later candles. Gaps are not filled. Recalculation of the same inputs, parameters, and calculator version does not create another row. The read API does not call the provider or run a calculator. No language-model measurement, probability, or trade recommendation is produced. Market profile, order flow, and derivatives stay unimplemented. Execution stays disabled and custody stays none.

## D018 — Evidence identity includes the candle-content fingerprint

Date: 2026-10-16
Status: accepted

The first evidence identity omitted the candle values. A corrected candle at the same observation time could collide with the old result and keep it as a conflict. Each calculation now stores a SHA-256 of the canonical candle id, timestamps, and OHLC volume. The same fingerprint is a duplicate, or a conflict if the result payload disagrees. A new fingerprint inserts another row and leaves the previous evidence unchanged.

## D019 — Spot and USD-M perpetual are different markets

Date: 2026-10-23
Status: accepted

Decision: keep spot BTC/USDT and USD-M BTCUSDT perpetual as separate identities, even though both use the provider symbol text `BTCUSDT`.

Reason: `BTC_USDT_SPOT` is `binance_spot`, market type `spot`, canonical symbol `BTC/USDT`. `BTC_USDT_USD_M_PERPETUAL` is `binance_usdm`, market type `perpetual`, canonical symbol `BTCUSDT-PERP`. Funding ingest refuses to write unless exchange info confirms `contractType=PERPETUAL`.

Consequence: spot candles, spot trades, and observed volume must not be labeled perpetual. Funding must not be written onto the spot instrument. D016 remains the Phase 2 spot decision.

## D020 — Aggregate-trade clock-window completeness stays unknown

Date: 2026-10-23
Status: accepted

Decision: record spot aggregate trades without promoting a retrieval to a complete clock window.

Reason: Binance aggregate, first, and last trade ids are not documented as a gap-free ledger, and a short page does not prove the window is exhausted. The completeness enum still names `COMPLETE` and `GAP_DETECTED`. `assess_aggregate_completeness` does not return either. A successful retrieval stays `COMPLETENESS_UNKNOWN`, including when aggregate ids are discontinuous. An empty response is not proof the market was idle.

Consequence: later calculators may use only stored rows, and they must keep the coverage limitation. Phase 3B is closed only with this semantic fix included (`b4903c5f72c3d0a327ab6a7ae6411e59fc5e434c`).

## D021 — Exact-price observed volume before any market-profile claim

Date: 2026-10-23
Status: accepted

Decision: Phase 3C sums stored aggregate base quantity at the exact trade price. It does not build a market profile.

Reason: the bucket method is `exact_price` and the volume definition is `base_quantity`. There is no time-price opportunity, no value area, no VAH/VAL, and no HVN/LVN. `buyer_is_maker` is stored for identity and is not summed as bid or ask size.

Consequence: the Research "Market Profile" section may show this observation. That display is not a market profile. D017 remains the Phase 3A record that market profile and order flow were not part of 3A. They are still not implemented.

## D022 — Observed POC is not a session or complete-market POC

Date: 2026-10-23
Status: accepted

Decision: the observed point of control is the exact stored price with the greatest summed base quantity in the requested window. A tie selects the lower price and is flagged.

Reason: the input is stored aggregate trades. Complete clock-window coverage is not proven. There is no session calendar. A conflicting aggregate payload produces no POC. A capped read produces no profile.

Consequence: `observed_poc_price` must not be treated as a session POC, a value-area center, or a trade level.

## D023 — Funding is the first perpetual-specific evidence

Date: 2026-10-23
Status: accepted

Decision: the first USD-M evidence family is public historical funding, not a perpetual price series.

Reason: Phase 3D stores `GET /fapi/v1/fundingRate` rows for `BTCUSDT-PERP` only. The adapter does not persist `markPrice`. There are no perpetual candles, trades, open interest, basis, or liquidation rows.

Consequence: perpetual evidence at this checkpoint is funding observations and window metadata. D017 said derivatives stayed unimplemented. That sentence is the 3A record. Funding is the later, narrow exception. Other derivatives remain unimplemented.

## D024 — Funding cadence is not invented, and a missing row is not zero

Date: 2026-10-23
Status: accepted

Decision: do not hard-code a funding interval, do not fill a missing timestamp, and do not store a zero rate for an empty window.

Reason: the provider response does not prove every charge was returned. Regular and Special rows are stored as accepted. Spacing between timestamps is not classified as a gap. An empty provider window is `EMPTY` and writes no rate.

Consequence: absence stays absence. It is not a 0% funding print and not proof the market had no funding.

## D025 — Funding-history completeness stays unknown

Date: 2026-10-23
Status: accepted

Decision: a successful funding retrieval is `COMPLETENESS_UNKNOWN`.

Reason: the history route does not document a complete archive. `assess_funding_completeness` has no complete status. `market_funding_windows` allows only `COMPLETENESS_UNKNOWN`, `EMPTY`, and `INVALID`. Conflicts and pagination that makes no progress are invalid and do not replace a stored rate.

Consequence: a populated funding table is not a claim that the archive is exhaustive. The read API does not call the provider.

## D026 — Funding is evidence, not a direction

Date: 2026-10-23
Status: accepted

Decision: a funding rate is a stored observation. It is not a long, short, crowded, bullish, or bearish signal.

Reason: the funding module records the rate, the time, and the rate type. It does not map the sign to a trade. The research panel shows the limitation text and does not recommend a side.

Consequence: a later phase must not convert funding into a trade direction unless quant validation and the rest of the decision chain exist. They do not exist at this checkpoint.

## D027 — Execution and custody stay closed after Phase 3D

Date: 2026-10-23
Status: accepted

Decision: evidence work does not enable execution or custody.

Reason: `EXECUTION_ENABLED` is `False`, `CUSTODY` is `none`, withdrawal permission is false, the risk engine raises, and the gateway raises. There is no order route. Controlled execution remains the later roadmap sequence: identity gate, read-only exchange access, paper and testnet, then an explicitly armed live path. None of that sequence is started.

Consequence: Phase 3D on `98f8c65235385028c20ef05d449637b9b0af8944` does not authorize trading, a wallet, or a withdrawal scope.
