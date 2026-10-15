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
