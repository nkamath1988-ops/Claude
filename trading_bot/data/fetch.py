"""Historical OHLCV data fetching from Binance's public REST API, with local CSV caching.

No API key required (public market-data endpoints only). Binance limits each request to
1000 candles, so multi-year history requires pagination across sequential time windows.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data_cache"

_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "num_trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]

_INTERVAL_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000,
    "4h": 14_400_000, "1d": 86_400_000,
}


def _cache_path(symbol: str, interval: str) -> Path:
    return CACHE_DIR / f"{symbol}_{interval}.csv"


def fetch_klines(symbol: str, interval: str, start: str, end: str | None = None,
                  use_cache: bool = True, request_pause_s: float = 0.3) -> pd.DataFrame:
    """Fetch OHLCV candles for `symbol` (e.g. 'BTCUSDT') at `interval` (e.g. '1d')
    from `start` (ISO date, e.g. '2019-01-01') through `end` (default: now).

    Returns a DataFrame indexed by UTC timestamp with columns:
    open, high, low, close, volume (all float).
    """
    if interval not in _INTERVAL_MS:
        raise ValueError(f"unsupported interval {interval!r}; choose from {sorted(_INTERVAL_MS)}")

    cache_file = _cache_path(symbol, interval)
    if use_cache and cache_file.exists():
        cached = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        if cached.index.min() <= pd.Timestamp(start, tz="UTC") and (
            end is None or cached.index.max() >= pd.Timestamp(end, tz="UTC") - pd.Timedelta(_INTERVAL_MS[interval], unit="ms")
        ):
            return cached.loc[start:end]

    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    end_ms = int(pd.Timestamp(end, tz="UTC").timestamp() * 1000) if end else int(time.time() * 1000)
    step_ms = _INTERVAL_MS[interval] * 1000  # 1000 candles per request

    rows = []
    cursor = start_ms
    session = requests.Session()
    while cursor < end_ms:
        window_end = min(cursor + step_ms, end_ms)
        resp = session.get(BINANCE_KLINES_URL, params={
            "symbol": symbol, "interval": interval,
            "startTime": cursor, "endTime": window_end, "limit": 1000,
        }, timeout=20)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            cursor = window_end
            continue
        rows.extend(batch)
        last_open_time = batch[-1][0]
        cursor = last_open_time + _INTERVAL_MS[interval]
        if len(batch) < 1000:
            cursor = max(cursor, window_end)
        time.sleep(request_pause_s)

    if not rows:
        raise RuntimeError(f"no data returned for {symbol} {interval} {start}..{end}")

    df = pd.DataFrame(rows, columns=_COLUMNS)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("open_time")[["open", "high", "low", "close", "volume"]].astype(float)
    df = df[~df.index.duplicated(keep="first")].sort_index()

    CACHE_DIR.mkdir(exist_ok=True)
    df.to_csv(cache_file)
    return df.loc[start:end]
