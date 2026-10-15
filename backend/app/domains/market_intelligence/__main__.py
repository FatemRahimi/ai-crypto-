"""Calculate technical evidence from candles already stored by Phase 2.

Example:

    python -m app.domains.market_intelligence --interval 1m --type swing_structure
"""

from __future__ import annotations

import argparse

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.domains.market_data.identity import SUPPORTED_INTERVALS
from app.domains.market_intelligence.calculators import EVIDENCE_TYPES
from app.domains.market_intelligence.service import TechnicalEvidenceService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calculate stored BTC/USDT technical evidence.")
    parser.add_argument("--interval", default="1m", choices=SUPPORTED_INTERVALS)
    parser.add_argument("--type", default="swing_structure", choices=(*EVIDENCE_TYPES, "all"))
    parser.add_argument("--candle-limit", type=int, default=100)
    parser.add_argument("--left", type=int, default=2)
    parser.add_argument("--right", type=int, default=2)
    args = parser.parse_args(argv)
    selected = EVIDENCE_TYPES if args.type == "all" else (args.type,)
    service = TechnicalEvidenceService.from_settings(get_settings())
    try:
        for evidence_type in selected:
            report = service.calculate(
                evidence_type,
                args.interval,
                candle_limit=args.candle_limit,
                left=args.left,
                right=args.right,
            )
            print(
                f"type={evidence_type} status={report.data_status} "
                f"inserted={report.inserted} duplicates={report.duplicates} "
                f"conflicts={report.conflicts}"
            )
            if report.conflicts:
                return 1
    except ValueError as exc:
        print(exc)
        return 2
    except SQLAlchemyError:
        print("technical evidence store is unavailable")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
