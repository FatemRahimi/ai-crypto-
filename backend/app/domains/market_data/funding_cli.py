"""Ingest a bounded USD-M BTCUSDT perpetual funding window.

Example:

    python -m app.domains.market_data.funding_cli --start START --end END
"""

from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.domains.market_data.funding_service import DEFAULT_MAX_FUNDING_ROWS, FundingDataService
from app.domains.market_data.providers.base import MarketDataProviderError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest public USD-M BTCUSDT funding history.")
    parser.add_argument("--start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--end", type=datetime.fromisoformat, required=True)
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_FUNDING_ROWS)
    args = parser.parse_args(argv)
    service = FundingDataService.from_settings(get_settings())
    try:
        report = service.ingest(start=args.start, end=args.end, max_rows=args.max_rows)
    except (ValueError, MarketDataProviderError, SQLAlchemyError) as exc:
        print(type(exc).__name__)
        return 1
    print(
        f"completeness={report.completeness.value} inserted={report.inserted} "
        f"duplicates={report.duplicates} conflicts={report.conflicts} rows={report.row_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
