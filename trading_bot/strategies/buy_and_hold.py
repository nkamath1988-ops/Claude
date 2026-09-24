import pandas as pd

from .base import Strategy


class BuyAndHold(Strategy):
    """Benchmark, not a strategy: buy on day one, never sell.

    Included because it is the null hypothesis every active strategy has to beat
    after fees and slippage — and on a secular-uptrend asset like BTC/ETH over long
    windows, most short-horizon retail strategies fail to clear that bar.
    """

    name = "buy_and_hold"

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(1, index=df.index)
