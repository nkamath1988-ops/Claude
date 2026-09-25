import pandas as pd


def dip_buy_entry_signal(df: pd.DataFrame, lookback_days: int = 20, pullback_pct: float = 0.10) -> pd.Series:
    """"Buy low" trigger: true on day t if close[t] has fallen at least `pullback_pct`
    below the highest HIGH of the trailing `lookback_days` (inclusive of day t) --
    e.g. lookback_days=20, pullback_pct=0.10 means "at least 10% off its 20-day high".

    Causal by construction (`.rolling(window)` at row t only uses rows <= t), so no
    lookahead: this is checked the same way as every other strategy's signal.

    Known failure mode: this is the same underlying bet as `rsi_reversion` -- that a
    dip is noise around a level price will return to, not the start of a real move
    down. In a genuine downtrend, "10% off the recent high" keeps re-triggering on the
    way to a 50%+ drawdown, buying every leg of a decline that hasn't found a floor.
    A fixed take-profit on the exit side does not fix this: it only determines how
    the WINNING trades are closed, not whether the entries themselves are picking
    real bottoms or falling knives -- rsi_reversion lost on every evaluation in this
    repo's history for exactly this reason, and this strategy is not a different bet.
    """
    rolling_high = df["high"].rolling(lookback_days).max()
    return df["close"] <= rolling_high * (1 - pullback_pct)
