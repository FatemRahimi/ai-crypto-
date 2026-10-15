# Data architecture

Phase 1 chooses where data will live. It does not invent the data.

## Stores

| Store | Phase 1 | Later role |
| --- | --- | --- |
| PostgreSQL | Engine, Alembic, readiness probe. No domain tables. | System of record for strategies, evidence metadata, decisions, and audit. |
| Browser memory | Strategy form state until refresh. | Never a system of record. |
| Exchange | Not connected. | System of record for balances, positions, and fills once read-only access exists. |
| Object or columnar store | Not introduced. | Candidate for high-volume ticks or footprints if PostgreSQL stops being the right shape. |

Adding a second database, a warehouse, or a bus requires a recorded decision. Phase 1 does not need one.

## Future classes of data

Raw observations and derived values stay apart.

- Raw: trades, candles, funding, open interest, liquidations, as received, with source and ingestion time.
- Derived: profile nodes, swings, regime labels, backtest metrics. Each row points at the raw ids or snapshot it used.
- Decisions: proposals, quant validations, risk decisions, policy decisions, intents. Immutable once written. A correction is a new row.
- Secrets: not in the tables above. A later credential table stores ciphertext only.

The browser receives copies for display. It is not allowed to be the only copy of a decision.

## Identifiers

Evidence references are `{ source, ref }`. `source` is a slug for a store the platform controls, such as a future `candle_store`. It is not a sentence and it is not a model name.

Instruments in the proposal contract are uppercase symbols of bounded length, for example `BTCUSDT`. The symbol is an identifier, not a price.

## What is not stored

- Sample UI copy
- Exchange API secrets
- Fabricated candles to fill a gap
- Language-model transcripts as if they were market observations

## Migration rule

Alembic revisions are the only schema change path. Revision `20261014_0001` is intentionally empty of domain tables. The next revision should belong to the first domain that truly persists something, which is expected to be market data or the identity gate, not a speculative schema for every future table.

## Readiness

`/health/live` means the process can answer. `/health/ready` means PostgreSQL accepted a `SELECT 1` within the connection timeout. A failed probe is logged as `database_unavailable` plus the exception class. The URL is not logged.

## Local database

`docker-compose.yml` starts PostgreSQL 16 for development. The application runs on the host so a Windows virtual environment and `npm run dev` stay ordinary. The compose file is not a production deployment.
