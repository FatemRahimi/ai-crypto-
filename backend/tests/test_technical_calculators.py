from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from app.domains.market_intelligence.calculators import (
    CALCULATOR_VERSION,
    EvidenceStatus,
    InputCandle,
    evaluate,
    input_fingerprint,
)
from app.domains.market_intelligence.service import evidence_freshness

OPEN = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
PARAMS = {"left": 1, "right": 1, "candle_limit": 10}


def _candle(
    index: int,
    high: str,
    low: str,
    *,
    close: str | None = None,
    volume: str = "2",
    step: timedelta = timedelta(minutes=1),
    open_time: datetime | None = None,
) -> InputCandle:
    opened = OPEN + (step * index) if open_time is None else open_time
    low_price = Decimal(low)
    return InputCandle(
        candle_id=index + 1,
        open_time=opened,
        close_time=opened + timedelta(seconds=59, milliseconds=999),
        open=low_price,
        high=Decimal(high),
        low=low_price,
        close=low_price if close is None else Decimal(close),
        volume=Decimal(volume),
    )


def _series(highs: list[str], lows: list[str]) -> list[InputCandle]:
    return [
        _candle(index, high, low)
        for index, (high, low) in enumerate(zip(highs, lows, strict=True))
    ]


def _rows(result: dict[str, object], key: str) -> list[dict[str, object]]:
    value = result[key]
    if not isinstance(value, list):
        raise AssertionError(key)
    rows: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AssertionError(key)
        rows.append(item)
    return rows


def test_pivot_is_absent_until_the_confirming_candle_exists() -> None:
    partial = _series(["5", "6", "5", "9"], ["1", "1", "1", "1"])
    early = evaluate("swing_structure", partial, "1m", PARAMS)
    assert early.data_status is EvidenceStatus.VALID
    assert "9" not in [item["price"] for item in _rows(early.result, "pivots")]
    complete = _series(["5", "6", "5", "9", "4"], ["1", "1", "1", "1", "1"])
    later = evaluate("swing_structure", complete, "1m", PARAMS)
    confirmed = [item for item in _rows(later.result, "pivots") if item["price"] == "9"]
    assert len(confirmed) == 1
    assert confirmed[0]["confirmed_at"] == _candle(4, "4", "1").close_time.isoformat().replace(
        "+00:00", "Z"
    )
    assert confirmed[0]["confirmed_at"] != confirmed[0]["pivot_open_time"]


def test_structure_labels_are_factual_and_not_orders() -> None:
    higher = evaluate(
        "swing_structure",
        _series(["5", "8", "5", "10", "4"], ["1", "1", "1", "1", "1"]),
        "1m",
        PARAMS,
    )
    lower = evaluate(
        "swing_structure",
        _series(["5", "10", "5", "8", "4"], ["1", "1", "1", "1", "1"]),
        "1m",
        PARAMS,
    )
    higher_low = evaluate(
        "swing_structure",
        _series(["9", "9", "9", "9", "9"], ["5", "2", "4", "3", "4"]),
        "1m",
        PARAMS,
    )
    lower_low = evaluate(
        "swing_structure",
        _series(["9", "9", "9", "9", "9"], ["5", "3", "4", "2", "4"]),
        "1m",
        PARAMS,
    )
    equal = evaluate(
        "swing_structure",
        _series(["5", "8", "5", "8", "4"], ["1", "1", "1", "1", "1"]),
        "1m",
        PARAMS,
    )
    assert [item["label"] for item in _rows(higher.result, "structure")] == ["higher_high"]
    assert [item["label"] for item in _rows(lower.result, "structure")] == ["lower_high"]
    assert [item["label"] for item in _rows(higher_low.result, "structure")] == ["higher_low"]
    assert [item["label"] for item in _rows(lower_low.result, "structure")] == ["lower_low"]
    assert [item["label"] for item in _rows(equal.result, "structure")] == ["equal_high"]
    assert "BUY" not in str(higher.result)
    assert "LONG" not in str(higher.result)


def test_support_counts_exact_pivot_prices_without_a_strength_label() -> None:
    draft = evaluate(
        "support_resistance",
        _series(["9", "9", "9", "9", "9"], ["5", "2", "4", "2", "4"]),
        "1m",
        PARAMS,
    )
    assert draft.result["levels"] == [
        {"role": "support", "price": "2", "touch_count": 2, "candle_ids": [2, 4]}
    ]
    assert "strong" not in draft.result


def test_short_history_is_insufficient_and_a_gap_is_not_filled() -> None:
    short = evaluate(
        "swing_structure",
        _series(["5", "6", "5", "9"], ["1", "1", "1", "1"]),
        "1m",
        {"left": 2, "right": 2, "candle_limit": 10},
    )
    assert short.data_status is EvidenceStatus.INSUFFICIENT
    assert short.result["pivots"] == []
    gapped = [
        _candle(0, "5", "1"),
        _candle(1, "6", "1"),
        _candle(3, "4", "1"),
    ]
    ranged = evaluate("range_statistics", gapped, "1m", {"candle_limit": 10})
    assert ranged.data_status is EvidenceStatus.GAP_DETECTED
    assert "high" not in ranged.result
    assert ranged.result["gap_count"] == 1


def test_range_and_vwap_stay_in_decimal_and_name_the_proxy() -> None:
    candles = [
        _candle(0, "1.30", "1.00", close="1.20", volume="2"),
        _candle(1, "1.10", "1.00", close="1.00", volume="2"),
    ]
    ranged = evaluate("range_statistics", candles, "1m", {"candle_limit": 10})
    assert ranged.result["range"] == "0.30"
    assert ranged.result["midpoint"] == "1.15"
    assert Decimal(str(ranged.result["percentage_range"])) == Decimal("30")
    vwap = evaluate(
        "candle_vwap",
        [_candle(0, "3", "1", close="2", volume="4")],
        "1m",
        {"candle_limit": 10},
    )
    assert vwap.result["vwap"] == "2"
    assert vwap.result["limitation"] == "candle_proxy_not_trade_vwap"
    assert vwap.result["price_proxy"] == "hlc3"
    empty_volume = evaluate(
        "candle_vwap",
        [_candle(0, "3", "1", close="2", volume="0")],
        "1m",
        {"candle_limit": 10},
    )
    assert empty_volume.data_status is EvidenceStatus.INSUFFICIENT
    assert "vwap" not in empty_volume.result


def test_repeated_calculation_matches_and_bad_clocks_are_rejected() -> None:
    candles = _series(["5", "8", "5", "10", "4"], ["1", "1", "1", "1", "1"])
    assert evaluate("swing_structure", candles, "1m", PARAMS) == evaluate(
        "swing_structure", candles, "1m", PARAMS
    )
    duplicate = [candles[0], candles[0]]
    assert evaluate("range_statistics", duplicate, "1m", {"candle_limit": 10}).data_status is (
        EvidenceStatus.INVALID
    )
    naive = _candle(0, "5", "1", open_time=datetime(2026, 10, 15, 12, 0))
    assert evaluate("range_statistics", [naive], "1m", {"candle_limit": 10}).data_status is (
        EvidenceStatus.INVALID
    )
    shifted = _candle(
        0,
        "5",
        "1",
        open_time=datetime(2026, 10, 15, 13, 0, tzinfo=timezone(timedelta(hours=1))),
    )
    draft = evaluate("range_statistics", [shifted], "1m", {"candle_limit": 10})
    assert draft.observation_time is not None
    assert draft.observation_time.utcoffset() == timedelta(hours=1)
    assert draft.calculator_version == CALCULATOR_VERSION


def test_input_fingerprint_changes_only_when_candle_content_changes() -> None:
    candle = _candle(0, "5", "1", close="1.5")
    changed = InputCandle(
        candle_id=candle.candle_id,
        open_time=candle.open_time,
        close_time=candle.close_time,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=Decimal("1.6"),
        volume=candle.volume,
    )
    assert input_fingerprint([candle]) == input_fingerprint([candle])
    assert input_fingerprint([candle, _candle(1, "6", "1")]) == input_fingerprint(
        [_candle(1, "6", "1"), candle]
    )
    assert input_fingerprint([candle]) != input_fingerprint([changed])
    assert len(input_fingerprint([candle])) == 64


def test_stale_observation_is_not_described_as_fresh() -> None:
    closed = OPEN + timedelta(minutes=1)
    assert evidence_freshness("VALID", closed, "1m", closed + timedelta(minutes=3)) == "stale"
    assert evidence_freshness("VALID", closed, "1m", closed + timedelta(seconds=30)) == "fresh"
    assert evidence_freshness("GAP_DETECTED", closed, "1m", closed) == "gap"
    assert evidence_freshness("INSUFFICIENT", closed, "1m", closed) == "insufficient"
