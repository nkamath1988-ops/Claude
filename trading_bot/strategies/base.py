from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """A strategy maps an OHLCV history to a target position at each bar.

    generate_signals(df) must use only data available up to and including each
    row's own timestamp (rolling/expanding windows satisfy this automatically —
    do not use .shift(-n) or any future row). The backtest engine is responsible
    for lagging the signal by one bar before it affects returns, so strategies
    should NOT lag their own output.
    """

    name: str = "unnamed"

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Return a Series indexed like df with values in {0, 1}: 1 = fully long, 0 = flat."""
        raise NotImplementedError
