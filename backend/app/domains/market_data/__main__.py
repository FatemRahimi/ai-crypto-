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
from app.domains.market_data.service import DEFAULT_MAX_CANDLES, MarketDataService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest public BTC/USDT spot market data.")
    parser.add_argument("--dataset", choices=("candles", "trades", "book"), default="candles")
    parser.add_argument("--interval", default="1m", choices=SUPPORTED_INTERVALS)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-candles", type=int, default=DEFAULT_MAX_CANDLES)
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


if __name__ == "__main__":
    raise SystemExit(main())
