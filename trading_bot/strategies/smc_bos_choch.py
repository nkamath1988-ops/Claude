"""SMC "BOS continuation + CHoCH exit" strategy -- the trade rule the user
confirmed: enter long on the pullback that follows a bullish Break of
Structure (the pullback's end is marked by the next swing low confirming
*higher* than the prior one, i.e. a new HL / strong low), exit to flat on a
bearish Change of Character (price closing back below that strong low).

Long-only by design, matching the rule's name ("CHoCH exit", not "CHoCH
flip"): a bearish CHoCH closes the position; going short again requires a
fresh bullish break and its own HL pullback, exactly like any other entry.

CHoCH exit alone has no time limit -- the first backtest run found trades
holding 6-13 weeks waiting for a reversal signal, well past the requested
1-2 week swing horizon. `max_holding_bars` adds a hard time-based exit on top
of CHoCH, so a stalled trade is cut loose rather than left open indefinitely;
the user asked for exiting early to be preferred over waiting out a slow
CHoCH. Bar count, not calendar time, since bars/day varies with the data
source (SPY/IWM: 2/day; SPX: ~2.1/day) -- 20 bars is a ~2-week approximation
at that rate, not an exact calendar cap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy
from .smc_structure import process_structure


class SmcBosChochStrategy(Strategy):
    """Long-only SMC swing strategy: BOS continuation entries, exit on
    whichever comes first of a bearish CHoCH or `max_holding_bars`.

    Known limitation shared with any swing-point-based structure detector:
    swing points need `swing_length` bars after they form to confirm (see
    smc_structure.py), so entries lag the actual turning point by that many
    bars -- this is the cost of having no lookahead, not a bug.
    """

    def __init__(self, swing_length: int = 3, max_holding_bars: int = 20):
        self.swing_length = swing_length
        self.max_holding_bars = max_holding_bars
        self.name = f"smc_bos_choch_{swing_length}_{max_holding_bars}"

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        structure = process_structure(df, self.swing_length)
        hl_confirmed = structure["hl_confirmed"].to_numpy()
        choch = structure["choch"].to_numpy()
        trend = structure["trend"].to_numpy()

        position = 0
        bars_held = 0
        out = np.zeros(len(df), dtype=int)
        for i in range(len(df)):
            if position == 0 and hl_confirmed[i] and trend[i] == "bullish":
                position = 1
                bars_held = 0
            elif position == 1:
                bars_held += 1
                if choch[i] or bars_held >= self.max_holding_bars:
                    position = 0
            out[i] = position
        return pd.Series(out, index=df.index)
