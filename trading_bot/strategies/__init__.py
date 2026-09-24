from .base import Strategy
from .buy_and_hold import BuyAndHold
from .sma_crossover import SmaCrossover
from .rsi_reversion import RsiMeanReversion
from .donchian_breakout import DonchianBreakout

ALL_STRATEGIES = [BuyAndHold(), SmaCrossover(), RsiMeanReversion(), DonchianBreakout()]

__all__ = [
    "Strategy", "BuyAndHold", "SmaCrossover", "RsiMeanReversion", "DonchianBreakout",
    "ALL_STRATEGIES",
]
