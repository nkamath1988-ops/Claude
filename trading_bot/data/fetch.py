"""Historical OHLCV data fetching from Coinbase Exchange's public REST API, with local
CSV caching.

No API key required (public market-data endpoints only). Binance was tried first but
had two problems in this environment: api.binance.com returns HTTP 451 ("restricted
location") regardless of network policy, and api.binance.us has a ~586-day gap in its
BTCUSD/ETHUSD history (mid-2023 to early-2025, coinciding with Binance.US losing USD
banking rails in 2023) -- a naive pct_change() across that gap produced a fake +285%
"one-day return" that silently corrupted volatility/Sharpe. Coinbase Exchange's history
was verified gap-free for BTC-USD/ETH-USD from 2020-01-01 onward before switching.

Coinbase limits each request to 300 candles, so multi-year history requires pagination
across sequential time windows.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product}/candles"
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data_cache"

_GRANULARITY_S = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}
_MAX_CANDLES_PER_REQUEST = 300


def _cache_path(symbol: str, interval: str) -> Path:
    return CACHE_DIR / f"{symbol}_{interval}.csv"


def _to_product(symbol: str) -> str:
    """'BTCUSD' -> 'BTC-USD'; pass through anything already containing a hyphen."""
    if "-" in symbol:
        return symbol
    if symbol.upper().endswith("USD"):
        return f"{symbol[:-3].upper()}-USD"
    raise ValueError(f"cannot infer Coinbase product id from symbol {symbol!r}; pass e.g. 'BTC-USD' directly")


def _assert_no_gaps(df: pd.DataFrame, interval: str, symbol: str) -> None:
    expected = pd.Timedelta(seconds=_GRANULARITY_S[interval])
    gaps = df.index.to_series().diff().dropna()
    bad = gaps[gaps > expected]
    if not bad.empty:
        raise RuntimeError(
            f"{symbol} {interval} data has {len(bad)} gap(s) larger than one bar "
            f"(largest: {bad.max()} at {bad.idxmax()}); refusing to backtest across a "
            f"gap since pct_change() would fabricate a single giant return there. "
            f"Inspect data_cache/{symbol}_{interval}.csv or narrow --start/--end."
        )


def fetch_klines(symbol: str, interval: str, start: str, end: str | None = None,
                  use_cache: bool = True, request_pause_s: float = 0.35) -> pd.DataFrame:
    """Fetch OHLCV candles for `symbol` (e.g. 'BTCUSD' or 'BTC-USD') at `interval`
    (e.g. '1d') from `start` (ISO date) through `end` (default: now).

    Returns a DataFrame indexed by UTC timestamp with columns open, high, low, close,
    volume (all float), sorted ascending, with no gaps larger than one bar -- a larger
    gap raises rather than silently letting pct_change() fabricate a huge fake return.
    """
    if interval not in _GRANULARITY_S:
        raise ValueError(f"unsupported interval {interval!r}; choose from {sorted(_GRANULARITY_S)}")

    product = _to_product(symbol)
    cache_file = _cache_path(symbol, interval)
    if use_cache and cache_file.exists():
        cached = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        start_ts, end_ts = pd.Timestamp(start, tz="UTC"), (pd.Timestamp(end, tz="UTC") if end else pd.Timestamp.now(tz="UTC"))
        if cached.index.min() <= start_ts and cached.index.max() >= end_ts - pd.Timedelta(seconds=_GRANULARITY_S[interval]):
            windowed = cached.loc[start:end]
            _assert_no_gaps(windowed, interval, symbol)
            return windowed

    granularity = _GRANULARITY_S[interval]
    cursor = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC") if end else pd.Timestamp.now(tz="UTC")
    step = pd.Timedelta(seconds=granularity * _MAX_CANDLES_PER_REQUEST)

    rows = []
    session = requests.Session()
    url = COINBASE_CANDLES_URL.format(product=product)
    while cursor < end_ts:
        window_end = min(cursor + step, end_ts)
        resp = session.get(url, params={
            "start": cursor.isoformat(), "end": window_end.isoformat(), "granularity": granularity,
        }, timeout=20)
        resp.raise_for_status()
        rows.extend(resp.json())
        cursor = window_end
        time.sleep(request_pause_s)

    if not rows:
        raise RuntimeError(f"no data returned for {symbol} {interval} {start}..{end}")

    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.drop_duplicates("time").set_index("time")[["open", "high", "low", "close", "volume"]].astype(float)
    df = df.sort_index()

    CACHE_DIR.mkdir(exist_ok=True)
    df.to_csv(cache_file)

    windowed = df.loc[start:end]
    _assert_no_gaps(windowed, interval, symbol)
    return windowed
