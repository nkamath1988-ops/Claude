"""Turn one raw row from a Robinhood scanner result into a suggested swing-trade
entry/stop/target -- a live, un-backtested suggestion, not a validated strategy.

Why ATR and not the scanner's own Support/Resistance columns: those returned at
least one real case (TT, scanned 2026-09-24) where the "Resistance" value sat
BELOW the live "Last" price -- price had already run past it. Presenting that as
a profit target would mean "your target is behind you," which is nonsensical, and
there was no way to tell in advance which rows would hit that. ATR (Average True
Range) is a plain volatility measure with an unambiguous meaning, so entry/stop/
target computed from it are at least internally consistent, even though they are
just as un-backtested as any other choice would be.

Why `close`, not `last`, is the entry reference: every scan filter (RSI, ADX,
% change) is computed from completed DAILY bars, not the live intraday quote. Using
`last` as the entry price would silently mix "the signal, as of yesterday's close"
with "today's price, which may have already moved for unrelated reasons" -- e.g.
TT's signal was computed at a $438.54 close, but by scan time `last` had already
drifted to $454.44, a 3.6% move the signal never priced in. `close` keeps the
entry consistent with what actually triggered the signal; `drift_pct` surfaces how
stale that basis already is, so a large drift is a reason to skip the name, not a
free extra gain.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SwingSuggestion:
    symbol: str
    entry_price: float
    stop_price: float
    target_price: float
    stop_pct: float
    target_pct: float
    reward_risk_ratio: float
    last_price: float
    drift_pct: float
    rsi: float
    adx: float
    atr: float


def suggest_entry_exit(row: dict, atr_stop_mult: float = 1.5, atr_target_mult: float = 3.0) -> SwingSuggestion:
    """`row` is one entry from a Robinhood create_scan/run_scan `results[i].columns`
    dict. Needs Close, Last, Average true range, RSI, Average directional index."""
    cols = row["columns"]
    symbol = row["ticker"]
    close = float(cols["Close"])
    last = float(cols["Last"])
    atr = float(cols["Average true range"])

    entry = close
    stop = entry - atr_stop_mult * atr
    target = entry + atr_target_mult * atr

    return SwingSuggestion(
        symbol=symbol,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        stop_pct=(stop / entry - 1),
        target_pct=(target / entry - 1),
        reward_risk_ratio=atr_target_mult / atr_stop_mult,
        last_price=last,
        drift_pct=(last / close - 1),
        rsi=float(cols["RSI"]),
        adx=float(cols["Average directional index (14)"]),
        atr=atr,
    )


def select_new_candidates(scan_results: list, open_symbols: set, max_new: int,
                           stale_drift_pct: float = 0.015,
                           atr_stop_mult: float = 1.5, atr_target_mult: float = 3.0) -> list:
    """From a fresh run_scan `results` list, pick up to `max_new` fresh (non-stale),
    not-already-held candidates, freshest signal first. Returns dicts shaped for
    stock_paper_trading.engine.advance_day's `new_candidates` argument."""
    fresh = []
    for row in scan_results:
        if row["ticker"] in open_symbols:
            continue
        s = suggest_entry_exit(row, atr_stop_mult, atr_target_mult)
        if abs(s.drift_pct) > stale_drift_pct:
            continue
        fresh.append(s)

    fresh.sort(key=lambda s: abs(s.drift_pct))
    return [{"symbol": s.symbol, "entry_price": s.entry_price,
              "stop_price": s.stop_price, "target_price": s.target_price}
             for s in fresh[:max_new]]
