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

## Phase 2 market observations

PostgreSQL remains the time-series store. TimescaleDB is not installed. The Phase 2 tables are `market_instruments`, `market_candles`, `market_trades`, and `market_book_snapshots`.

The only instrument in this phase is spot BTC quoted in USDT, provider `binance_spot`, provider symbol `BTCUSDT`, canonical symbol `BTC/USDT`. BTC/USD is a different market and is not implied.

Provider JSON is parsed at the adapter boundary and is not stored. A complete raw payload is unnecessary for this phase because each stored row keeps the provider, the public endpoint, the provider symbol, the source time, the ingestion time, and normalization version `binance-public-v1`. That is enough to audit how a canonical row was produced. Downstream queries read the canonical tables only.

Candle `open_time` is the provider open time in UTC. `close_time` is the provider close time in UTC. `ingested_at` is when this process accepted the row. A book snapshot from `GET /api/v3/ticker/bookTicker` has no source timestamp in the official payload, so `source_timestamp` stays null. Ingestion time is not copied into that column.

Persisted prices and quantities are `numeric(38, 18)`. A kline that is still open, fails OHLC checks, or uses an unsupported interval is not inserted. Re-ingesting the same candle or trade id does nothing. An unchanged book is not inserted again.

`VALID` is the only status written. `STALE` and `GAP_DETECTED` are calculated when data is read: a candle is stale when now is more than two intervals after its close, and a gap is a missing open time in a returned sequence. Gaps are not filled with synthetic candles.

Public host: `https://data-api.binance.vision`. Endpoints: `GET /api/v3/klines` (weight 2, limit max 1000), `GET /api/v3/trades` (weight 25, recent trades only), `GET /api/v3/ticker/bookTicker` (weight 2). Intervals `1m`, `5m`, `15m`, `1h`, `4h`, and `1d` are provider-native. Requests do not send `timeZone`, so kline buckets stay UTC. `startTime` and `endTime` are UTC milliseconds. A development ingest refuses a range above the candle cap (default 1000, hard maximum 5000) and pauses 250ms between kline pages. Transient HTTP 429 and 5xx responses retry up to three times with bounded backoff.

`isBuyerMaker` is stored as `buyer_is_maker`. The official description is whether the buyer was the maker. This phase does not translate that into a buy or sell signal.

The documented public trade stream `wss://data-stream.binance.vision/ws/btcusdt@trade` is not connected. Continuous streaming is Phase 2.1. Read routes never call the provider, so a provider outage leaves stored rows queryable and does not invent a replacement price.

Likely later pressure is tick volume, not request shape. Indexes are `(market_id, interval, open_time)` for candles and `(market_id, event_time)` for trades. Bulk candle inserts use one statement per batch.

## Phase 3A technical evidence

Phase 3A calculates deterministic evidence from verified `market_candles` rows. It does not store measurements on those rows. Market profile, order flow, derivatives, and language-model measurements are not implemented.

`technical_evidence` stores the evidence type, market, interval, observation time, calculation time, calculator name, calculator version `technical-evidence-v1`, canonical parameters and their SHA-256, the input candle id list and open-time span, the result JSON, and a stable data status. Observation time is the close time of the last input candle. Ingestion time is not used. Decimals are JSON strings.

A pivot high or low uses a strict fractal: the candle must exceed every neighbor in `left` earlier candles and `right` later candles. It is not emitted until those later candles exist. Confirmation time is the close of the last required later candle. Successive confirmed highs are labeled higher high, lower high, or equal high. Successive confirmed lows use the same comparison. Those labels are not orders.

Support and resistance candidates are the exact prices of confirmed pivot lows and highs. `touch_count` is how many confirmed pivots share that exact price. It is not a strength rating.

Range statistics are the maximum high, minimum low, their difference, their midpoint, and the difference as a percentage of the low. Candle VWAP is the volume-weighted average of `(high + low + close) / 3`, using candle base volume. It is labeled `candle_proxy_not_trade_vwap`. Zero total volume returns insufficient and no VWAP.

A missing candle in the input window returns `GAP_DETECTED` and no filled measurement. Too few candles, or no candles, returns insufficient; a run with no observation time is not stored. Duplicate open times and naive timestamps are invalid and are not stored. `VALID` measurements are marked stale when read if the observation is older than two intervals. The same market, type, interval, observation, calculator version, and parameters do not insert a second row. A different result for that identity is a conflict and the stored row is kept.

The supported intervals are the Phase 2 intervals. The calculators are shared across those intervals.

## Migration rule

Alembic revisions are the only schema change path. Revision `20261014_0001` is intentionally empty of domain tables. The next revision should belong to the first domain that truly persists something, which is expected to be market data or the identity gate, not a speculative schema for every future table.

## Readiness

`/health/live` means the process can answer. `/health/ready` means PostgreSQL accepted a `SELECT 1` within the connection timeout. A failed probe is logged as `database_unavailable` plus the exception class. The URL is not logged.

## Local database

`docker-compose.yml` starts PostgreSQL 16 for development. The application runs on the host so a Windows virtual environment and `npm run dev` stay ordinary. The compose file is not a production deployment.
