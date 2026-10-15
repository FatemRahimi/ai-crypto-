"""Turn one provider row into a canonical observation, or reject it."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.domains.market_data.identity import NORMALIZATION_VERSION, MarketIdentity
from app.domains.market_data.providers.binance_spot import BOOK_PATH, KLINES_PATH, TRADES_PATH
from app.domains.market_data.quality import (
    DataStatus,
    Rejection,
    is_closed_candle,
    parse_decimal,
    parse_millis,
    validate_candle_shape,
    validate_trade,
)
from app.domains.market_data.records import CanonicalBook, CanonicalCandle, CanonicalTrade


def normalize_kline(
    row: object,
    identity: MarketIdentity,
    interval: str,
    ingested_at: datetime,
    *,
    now: datetime,
) -> CanonicalCandle | Rejection:
    if not isinstance(row, list) or len(row) < 9:
        return Rejection("malformed kline")
    open_time = parse_millis(row[0], field="open_time")
    close_time = parse_millis(row[6], field="close_time")
    open_ = parse_decimal(row[1], field="open")
    high = parse_decimal(row[2], field="high")
    low = parse_decimal(row[3], field="low")
    close = parse_decimal(row[4], field="close")
    volume = parse_decimal(row[5], field="volume")
    quote_volume = parse_decimal(row[7], field="quote_volume")
    trade_count = row[8]
    parsed = (open_time, close_time, open_, high, low, close, volume, quote_volume)
    for item in parsed:
        if isinstance(item, Rejection):
            return item
    if isinstance(trade_count, bool) or not isinstance(trade_count, int) or trade_count < 0:
        return Rejection("trade_count must be a non-negative integer")
    assert isinstance(open_time, datetime)
    assert isinstance(close_time, datetime)
    assert isinstance(open_, Decimal)
    assert isinstance(high, Decimal)
    assert isinstance(low, Decimal)
    assert isinstance(close, Decimal)
    assert isinstance(volume, Decimal)
    assert isinstance(quote_volume, Decimal)
    problem = validate_candle_shape(
        interval=interval,
        open_time=open_time,
        close_time=close_time,
        open_=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        quote_volume=quote_volume,
    )
    if problem is not None:
        return problem
    if not is_closed_candle(close_time, now):
        return Rejection("candle is still open")
    return CanonicalCandle(
        provider=identity.provider,
        canonical_symbol=identity.canonical_symbol,
        provider_symbol=identity.provider_symbol,
        market_type=identity.market_type,
        quote_asset=identity.quote_asset,
        interval=interval,
        open_time=open_time,
        close_time=close_time,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        quote_volume=quote_volume,
        trade_count=trade_count,
        ingested_at=ingested_at,
        data_status=DataStatus.VALID,
        endpoint=f"GET {KLINES_PATH}",
        normalization_version=NORMALIZATION_VERSION,
    )


def normalize_trade(
    row: object,
    identity: MarketIdentity,
    ingested_at: datetime,
) -> CanonicalTrade | Rejection:
    if not isinstance(row, dict):
        return Rejection("malformed trade")
    trade_id = row.get("id")
    event_time = parse_millis(row.get("time"), field="event_time")
    price = parse_decimal(row.get("price"), field="price")
    quantity = parse_decimal(row.get("qty"), field="quantity")
    quote_quantity = parse_decimal(row.get("quoteQty"), field="quote_quantity")
    buyer_is_maker = row.get("isBuyerMaker")
    for item in (event_time, price, quantity, quote_quantity):
        if isinstance(item, Rejection):
            return item
    assert isinstance(event_time, datetime)
    assert isinstance(price, Decimal)
    assert isinstance(quantity, Decimal)
    assert isinstance(quote_quantity, Decimal)
    if isinstance(trade_id, bool) or not isinstance(trade_id, int):
        return Rejection("provider trade id must be an integer")
    if not isinstance(buyer_is_maker, bool):
        return Rejection("isBuyerMaker must be a boolean")
    problem = validate_trade(
        price=price,
        quantity=quantity,
        quote_quantity=quote_quantity,
        event_time=event_time,
    )
    if problem is not None:
        return problem
    return CanonicalTrade(
        provider=identity.provider,
        canonical_symbol=identity.canonical_symbol,
        provider_symbol=identity.provider_symbol,
        market_type=identity.market_type,
        provider_trade_id=trade_id,
        price=price,
        quantity=quantity,
        quote_quantity=quote_quantity,
        event_time=event_time,
        buyer_is_maker=buyer_is_maker,
        ingested_at=ingested_at,
        endpoint=f"GET {TRADES_PATH}",
        normalization_version=NORMALIZATION_VERSION,
    )


def normalize_book(
    row: object,
    identity: MarketIdentity,
    ingested_at: datetime,
) -> CanonicalBook | Rejection:
    if not isinstance(row, dict):
        return Rejection("malformed book ticker")
    if row.get("symbol") != identity.provider_symbol:
        return Rejection("book ticker symbol does not match the requested market")
    bid = parse_decimal(row.get("bidPrice"), field="bid")
    ask = parse_decimal(row.get("askPrice"), field="ask")
    bid_quantity = parse_decimal(row.get("bidQty"), field="bid_quantity")
    ask_quantity = parse_decimal(row.get("askQty"), field="ask_quantity")
    for item in (bid, ask, bid_quantity, ask_quantity):
        if isinstance(item, Rejection):
            return item
    assert isinstance(bid, Decimal)
    assert isinstance(ask, Decimal)
    assert isinstance(bid_quantity, Decimal)
    assert isinstance(ask_quantity, Decimal)
    if bid <= 0 or ask <= 0:
        return Rejection("negative or zero bid or ask")
    if ask < bid:
        return Rejection("ask is below bid")
    if bid_quantity < 0 or ask_quantity < 0:
        return Rejection("negative book quantity")
    return CanonicalBook(
        provider=identity.provider,
        canonical_symbol=identity.canonical_symbol,
        provider_symbol=identity.provider_symbol,
        market_type=identity.market_type,
        bid=bid,
        ask=ask,
        bid_quantity=bid_quantity,
        ask_quantity=ask_quantity,
        source_timestamp=None,
        ingested_at=ingested_at,
        endpoint=f"GET {BOOK_PATH}",
        normalization_version=NORMALIZATION_VERSION,
    )
