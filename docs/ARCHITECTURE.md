# Architecture

Phase 1 is one deployable API and one web application. It is a modular monolith. It is not a set of services.

## Runtime

```text
Browser (Next.js, TypeScript, React, Tailwind)
        │  HTTP, public API URL only
        ▼
FastAPI application
        │
        ├── health and platform routes
        ├── read-only market-data routes
        ├── domain boundaries
        └── PostgreSQL (connectivity and canonical market observations)
```

The browser never receives database credentials, `APP_SECRET_KEY`, or an exchange secret. The only frontend environment value is `NEXT_PUBLIC_API_URL`.

## Domain map

Each domain under `backend/app/domains/` owns a written boundary: what it is for, what it must not do, and whether Phase 1 behavior is `planned`, `foundation`, or `disabled`.

| Domain | Phase 1 status | Meaning |
| --- | --- | --- |
| identity | planned | No login or session |
| accounts | planned | No ledger and no custody |
| connections | planned | No exchange connection |
| market_data | foundation | Public BTC/USDT spot observations. No indicators. |
| market_intelligence | planned | No interpretation |
| strategies | planned | No stored or compiled strategy |
| quant | planned | No backtest or probability model |
| regimes | planned | No regime model |
| opportunities | planned | No evaluated opportunity |
| risk | disabled | Engine refuses every evaluation |
| capital | planned | No sizing |
| positions | planned | No position book |
| execution | disabled | Gateway refuses every intent |
| notifications | planned | No alert channel |
| performance | planned | No performance math |
| ai | foundation | Can construct a `TradeProposal` only |
| audit | planned | No audit table and no writer |

`GET /api/v1/platform` returns this map. It does not return market or account data.

There is no business logic hiding behind these packages. The behavior that exists is the proposal contract, the authorization choke point, the refusing risk engine, and the refusing gateway.

## Future decision path

```text
AI / strategy
    → TradeProposal
    → QuantValidation
    → RiskDecision          (decided_by = deterministic_risk_engine)
    → ExecutionPolicyDecision
    → ExecutionIntent       (no size, price, or secret)
    → ExecutionGateway.submit
    → Exchange adapter      (does not exist)
```

`authorize_execution` builds an `ExecutionIntent` only when the proposal is long or short, both the proposal and the quant result cite evidence, quant passed, risk approved, policy allows it, and the kill-switch flag is off. A policy that tries to allow execution while the kill switch is engaged is rejected at construction.

The gateway then refuses the intent. Building a token is not submission.

The AI package is scanned by test to ensure it does not reference the gateway, the intent type, or `authorize_execution`.

## API surface

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health/live` | Process is up. Does not touch the database. |
| GET | `/health/ready` | 200 when PostgreSQL answers `SELECT 1`, otherwise 503. Execution is reported disabled. |
| GET | `/api/v1/platform` | Phase, constitution flags, pipeline, domain boundaries. |
| GET | `/api/v1/market-data/status` | Stored BTC/USDT coverage, freshness, stream disconnected. |
| GET | `/api/v1/market-data/candles` | Verified candles in UTC order. Empty list when none are stored. |
| GET | `/api/v1/market-data/latest` | Newest verified trade or closed candle, or an explicit empty price. |
| GET | `/docs`, `/openapi.json` | Present when `APP_ENV` is `local` or `test`. Absent in `production`. |

CORS allows GET and OPTIONS from the configured origins only. Credentials are not allowed. There is no cookie session.

## Persistence

SQLAlchemy 2 and Alembic are wired. Revision `20261014_0001` creates no domain tables. Revision `20261015_0002` adds the market-observation tables. Strategies, orders, and audit rows are still absent. See `docs/DATA_ARCHITECTURE.md`.

Public ingestion is a manual command, not a background worker. The read API serves stored rows and does not call Binance during a request.

## Web application

Next.js App Router, strict TypeScript, Tailwind CSS. Seven routes share one shell:

Home, Strategy, Opportunities, Positions, Research, Performance, Account.

The home command center has two layers:

1. Honest Phase 1 answers: no verified market data, nothing evaluated, nothing to do.
2. A dashed demonstration layout, badged Demo, using sample words rather than prices.

Demo copy lives in the frontend. The API does not serve sample prices.

## What is deliberately absent

Kubernetes, message buses, microservices, a model runtime, exchange SDKs, order routes, wallet screens, and background workers.
