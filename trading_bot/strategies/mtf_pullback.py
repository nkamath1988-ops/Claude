import pandas as pd


def _resample_ohlc(df_5m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample 5m OHLCV up to a higher timeframe, labeling each bar at its CLOSE
    time (not the more common pandas default of the bar's start time). This matters:
    a bar labeled by its start time would let a signal at that label "see" its own
    still-forming bar's later 5m candles -- lookahead. Labeling by close time and then
    forward-filling (done by the caller) guarantees a higher-timeframe value only
    becomes visible at or after the moment that bar actually finished forming."""
    agg = df_5m.resample(rule, label="right", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return agg.dropna(subset=["close"])


def mtf_pullback_entry_signal(df_5m: pd.DataFrame, bias_fast: int = 20, bias_slow: int = 50,
                               pullback_period: int = 20) -> pd.Series:
    """Multi-timeframe long entry: the 4h chart sets trend bias (fast SMA above slow
    SMA = bullish, else flat/blocked -- this is long-only, so a bearish 4h bias just
    means "don't buy", not "sell short"), the 5m chart times the actual entry, on a
    pullback-and-reclaim of a short 5m moving average while that 4h bias is bullish.

    No-lookahead by construction: the 4h bias at 5m timestamp t is the most recently
    *closed* 4h bar as of t (see _resample_ohlc's close-time labeling + the forward
    fill below), never the 4h bar still forming at t. The 5m pullback trigger itself
    only uses data through row t (rolling/shift, both causal).

    Known failure mode: this is still fundamentally a trend-following + dip-buy
    combination, the same two mechanisms already tested elsewhere in this repo.
    The 4h trend filter should cut the worst of rsi_reversion's failure mode (buying
    dips *against* the prevailing trend, which is what actually sank it) by only
    buying pullbacks *within* an already-confirmed uptrend -- but it inherits
    sma_crossover's known weakness instead: choppy, sideways 4h action generates
    a bullish/bearish bias flip-flop, and every flip is a signal changing under you
    with no warning baked into the entry rule itself.
    """
    bars_4h = _resample_ohlc(df_5m, "4h")
    fast_sma = bars_4h["close"].rolling(bias_fast).mean()
    slow_sma = bars_4h["close"].rolling(bias_slow).mean()
    bullish_4h = (fast_sma > slow_sma).reindex(df_5m.index, method="ffill").fillna(False)

    pullback_ma = df_5m["close"].rolling(pullback_period).mean()
    reclaim = (df_5m["close"] > pullback_ma) & (df_5m["close"].shift(1) <= pullback_ma.shift(1))

    return (bullish_4h & reclaim).fillna(False)
