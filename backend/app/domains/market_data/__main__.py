"""Fetch a small public BTC range and store closed observations.

Example:

    python -m app.domains.market_data --interval 1m --limit 5
"""

from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.domains.market_data.identity import SUPPORTED_INTERVALS
from app.domains.market_data.providers.base import MarketDataProviderError
from app.domains.market_data.service import (
    DEFAULT_MAX_AGGREGATE_TRADES,
    DEFAULT_MAX_CANDLES,
    MarketDataService,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest public BTC/USDT spot market data.")
    parser.add_argument(
        "--dataset",
        choices=("candles", "trades", "book", "aggregate-trades"),
        default="candles",
    )
    parser.add_argument("--interval", default="1m", choices=SUPPORTED_INTERVALS)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-candles", type=int, default=DEFAULT_MAX_CANDLES)
    parser.add_argument("--max-aggregate-trades", type=int, default=DEFAULT_MAX_AGGREGATE_TRADES)
    parser.add_argument("--start", type=datetime.fromisoformat, default=None)
    parser.add_argument("--end", type=datetime.fromisoformat, default=None)
    args = parser.parse_args(argv)
    service = MarketDataService.from_settings(get_settings())
    try:
        if args.dataset == "candles":
            report = service.ingest_candles(
                args.interval,
                start=args.start,
                end=args.end,
                limit=args.limit,
                max_candles=args.max_candles,
            )
        elif args.dataset == "trades":
            report = service.ingest_recent_trades(limit=args.limit)
        elif args.dataset == "aggregate-trades":
            if args.start is None or args.end is None:
                print("ingest_refused reason=aggregate trades require --start and --end")
                return 2
            window = service.ingest_aggregate_trades(
                start=args.start,
                end=args.end,
                max_trades=args.max_aggregate_trades,
            )
            print(
                "market=BTC/USDT "
                f"provider={window.provider} "
                f"requested_start={window.requested_start.isoformat()} "
                f"requested_end={window.requested_end.isoformat()} "
                f"first_event_time={_stamp(window.first_event_time)} "
                f"last_event_time={_stamp(window.last_event_time)} "
                f"first_aggregate_id={window.first_aggregate_id} "
                f"last_aggregate_id={window.last_aggregate_id} "
                f"aggregate_trade_count={window.aggregate_trade_count} "
                f"underlying_first_trade_id={window.underlying_first_trade_id} "
                f"underlying_last_trade_id={window.underlying_last_trade_id} "
                f"inserted={window.inserted} duplicates={window.duplicates} "
                f"conflicts={window.conflicts} completeness={window.completeness.value} "
                f"checked_at={window.checked_at.isoformat()} "
                f"input_fingerprint={window.input_fingerprint}"
            )
            return 0
        else:
            report = service.ingest_book()
    except ValueError as exc:
        print(f"ingest_refused reason={exc}")
        return 2
    except (MarketDataProviderError, SQLAlchemyError) as exc:
        print(f"ingest_failed error_type={type(exc).__name__}")
        return 1
    summary = (
        f"inserted={report.inserted} duplicates={report.duplicates} "
        f"rejected={report.rejected} gaps={report.gaps}"
    )
    print(summary)
    return 0


def _stamp(value: datetime | None) -> str:
    if value is None:
        return "none"
    return value.isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
