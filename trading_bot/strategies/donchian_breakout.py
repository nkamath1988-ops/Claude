import numpy as np
import pandas as pd

from .base import Strategy


class DonchianBreakout(Strategy):
    """Momentum: go long on a new N-bar high, exit on a new N-bar low.

    Known failure mode: false breakouts in low-volume/low-liquidity conditions
    trigger entries right before price snaps back, so it eats a steady stream of
    small losses between the (less frequent) genuine trend runs that make it
    profitable overall. It needs the rare big trend to pay for many small failed
    breakouts — if that trend doesn't show up during the backtest window, the
    strategy looks purely like a fee-bleeding loser even though the logic is sound
    over a longer horizon.
    """

    name = "donchian_breakout"

    def __init__(self, lookback: int = 20):
        self.lookback = lookback
        self.name = f"donchian_breakout_{lookback}"

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        rolling_high = df["high"].rolling(self.lookback).max()
        rolling_low = df["low"].rolling(self.lookback).min()
        position = 0
        close = df["close"].to_numpy()
        hi = rolling_high.shift(1).to_numpy()
        lo = rolling_low.shift(1).to_numpy()
        out = np.zeros(len(df), dtype=int)
        for i in range(len(close)):
            if pd.notna(hi[i]) and pd.notna(lo[i]):
                if position == 0 and close[i] > hi[i]:
                    position = 1
                elif position == 1 and close[i] < lo[i]:
                    position = 0
            out[i] = position
        return pd.Series(out, index=df.index)
