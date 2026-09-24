import pandas as pd

from .base import Strategy


class SmaCrossover(Strategy):
    """Trend-following: long while the fast SMA is above the slow SMA, flat otherwise.

    Known failure mode: whipsaws hard in range-bound/choppy markets, where price
    oscillates around the moving averages and generates a stream of losing trades
    each paying the spread/fee twice. It also lags at turning points by construction
    (it only confirms a trend after it has already moved), giving back a chunk of
    every reversal before exiting. Parameters (fast/slow window) are easy to overfit
    to a specific backtest period.
    """

    name = "sma_crossover"

    def __init__(self, fast: int = 20, slow: int = 50):
        if fast >= slow:
            raise ValueError("fast window must be shorter than slow window")
        self.fast = fast
        self.slow = slow
        self.name = f"sma_crossover_{fast}_{slow}"

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        fast_sma = df["close"].rolling(self.fast).mean()
        slow_sma = df["close"].rolling(self.slow).mean()
        signal = (fast_sma > slow_sma).astype(int)
        signal[slow_sma.isna()] = 0
        return signal
