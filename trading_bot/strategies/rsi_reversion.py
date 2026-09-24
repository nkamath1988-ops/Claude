import numpy as np
import pandas as pd

from .base import Strategy


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


class RsiMeanReversion(Strategy):
    """Mean-reversion: buy when RSI shows oversold, sell (go flat) when it recovers
    to overbought.

    Known failure mode: this bets against the prevailing trend. Crypto assets spend
    long stretches in strong directional trends (both up and down) rather than
    mean-reverting around a stable level, so "buying the dip" during a genuine
    downtrend keeps buying into a falling market with no floor — the classic way
    mean-reversion strategies blow up. It tends to look great in choppy/sideways
    backtests and terrible in trending ones, which makes the backtest window choice
    do a lot of the work.
    """

    name = "rsi_reversion"

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 60):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.name = f"rsi_reversion_{period}_{int(oversold)}_{int(overbought)}"

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        rsi = _rsi(df["close"], self.period)
        position = 0
        rsi_vals = rsi.to_numpy()
        out = np.zeros(len(df), dtype=int)
        for i in range(len(rsi_vals)):
            if position == 0 and rsi_vals[i] < self.oversold:
                position = 1
            elif position == 1 and rsi_vals[i] > self.overbought:
                position = 0
            out[i] = position
        return pd.Series(out, index=df.index)
