"""Smart Money Concepts (SMC) market-structure detection: swing points, HH/HL/LH/LL
trend labeling, strong high/low, Break of Structure (BOS), and Change of Character
(CHoCH) -- built from the definitions the user gave verbatim:

  Bullish trend/OF - higher highs and higher lows
  Bearish trend/OF - lower lows and lower highs
  Swing high - highest point that caused the swing low
  Swing low - lowest point that caused the swing high
  Strong low - lows that caused highs (HL's)
  Strong high - highs that caused lows (LH's)
  After a break of structure (BOS) - expect a pullback on that timeframe
  CHoCH - bullish structure changing to bearish structure (vice versa)

Swing points are found with a symmetric fractal: bar i is a swing high if its
high is strictly greater than the `swing_length` bars on both sides of it (and
symmetric for swing lows, using the low). This means a swing point at bar i
cannot be confirmed until bar i + swing_length has printed -- there is no way
to know "nothing in the next swing_length bars exceeded it" any earlier. Every
downstream state (trend, BOS, CHoCH, strong high/low, HH/HL/LH/LL labels) is
applied starting only from `confirm_index` (= bar_index + swing_length), never
from the bar the swing actually occurred on, so the whole module is
lookahead-free when consumed causally (as process_structure does).

Trend/BOS/CHoCH are driven by price actually breaking a swing level (the
standard ICT/SMC definition the user's own BOS/CHoCH lines describe), not
merely by the HH/HL/LH/LL swing labels agreeing -- the two will usually line
up but the break-based state is what the trading rule ("BOS continuation +
CHoCH exit") acts on. HH/HL/LH/LL labels are exposed alongside as a diagnostic
that mirrors the user's literal swing definitions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd


def find_swing_points(df: pd.DataFrame, swing_length: int = 3) -> list[dict]:
    """Full-history batch pass (needs `swing_length` bars of future data per
    point, hence not itself causal) -- returns each swing as
    {"bar_index", "confirm_index", "price", "kind"} (kind: "high"/"low"),
    sorted by confirm_index so causal consumers can apply them in order.
    Ties within a window are skipped (neither side registers as *the* extreme)
    rather than guessing which bar was first."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)
    swings = []
    for i in range(swing_length, n - swing_length):
        window_high = highs[i - swing_length:i + swing_length + 1]
        if highs[i] == window_high.max() and (window_high == highs[i]).sum() == 1:
            swings.append({"bar_index": i, "confirm_index": i + swing_length,
                            "price": float(highs[i]), "kind": "high"})
        window_low = lows[i - swing_length:i + swing_length + 1]
        if lows[i] == window_low.min() and (window_low == lows[i]).sum() == 1:
            swings.append({"bar_index": i, "confirm_index": i + swing_length,
                            "price": float(lows[i]), "kind": "low"})
    swings.sort(key=lambda s: (s["confirm_index"], s["bar_index"]))
    return swings


@dataclass
class StructureBar:
    trend: str          # "bullish", "bearish", or "unknown" (no break yet)
    bos: bool           # this bar's close broke structure in the prevailing direction
    choch: bool         # this bar's close broke structure against the prevailing trend
    strong_low: float | None   # most recent HL that preceded a bullish break (None if none yet)
    strong_high: float | None  # most recent LH that preceded a bearish break
    hl_confirmed: bool  # a new, higher swing low was just confirmed (pullback-end candidate for longs)
    lh_confirmed: bool  # a new, lower swing high was just confirmed (pullback-end candidate for shorts)
    swing_label: str | None    # "HH"/"HL"/"LH"/"LL" if a swing confirmed this bar, else None


def process_structure(df: pd.DataFrame, swing_length: int = 3) -> pd.DataFrame:
    """Bar-by-bar causal structure engine. Returns a DataFrame indexed like df
    with the StructureBar fields as columns, each computed using only data
    available through that bar (see module docstring for the confirm-lag
    reasoning)."""
    swings = find_swing_points(df, swing_length)
    closes = df["close"].to_numpy()
    n = len(df)

    swings_by_confirm = defaultdict(list)
    for s in swings:
        swings_by_confirm[s["confirm_index"]].append(s)

    cur_trend = "unknown"
    last_high = None   # most recent confirmed swing-high dict, or None if already broken/unset
    last_low = None
    prior_high_price = None   # previous confirmed swing high's price, for HH/LH labeling
    prior_low_price = None
    cur_strong_low = None
    cur_strong_high = None

    rows = []
    for i in range(n):
        bos = False
        choch = False
        hl_confirmed = False
        lh_confirmed = False
        swing_label = None

        # 1. Check this bar's close against currently-known (already-confirmed) levels.
        bullish_break = last_high is not None and closes[i] > last_high["price"]
        bearish_break = last_low is not None and closes[i] < last_low["price"]

        if bullish_break:
            choch = cur_trend == "bearish"
            bos = not choch
            if last_low is not None:
                cur_strong_low = last_low["price"]
            cur_trend = "bullish"
            last_high = None  # consumed -- don't re-trigger on the same broken level
        elif bearish_break:
            choch = cur_trend == "bullish"
            bos = not choch
            if last_high is not None:
                cur_strong_high = last_high["price"]
            cur_trend = "bearish"
            last_low = None

        # 2. Apply any swings that become confirmed as of this bar.
        for s in swings_by_confirm.get(i, []):
            if s["kind"] == "high":
                is_hh = prior_high_price is None or s["price"] > prior_high_price
                swing_label = "HH" if is_hh else "LH"
                if not is_hh and cur_trend == "bearish":
                    lh_confirmed = True
                prior_high_price = s["price"]
                last_high = s
            else:
                is_hl = prior_low_price is None or s["price"] > prior_low_price
                swing_label = "HL" if is_hl else "LL"
                if is_hl and cur_trend == "bullish":
                    hl_confirmed = True
                prior_low_price = s["price"]
                last_low = s

        rows.append(StructureBar(
            trend=cur_trend, bos=bos, choch=choch,
            strong_low=cur_strong_low, strong_high=cur_strong_high,
            hl_confirmed=hl_confirmed, lh_confirmed=lh_confirmed,
            swing_label=swing_label,
        ))

    return pd.DataFrame(
        [{"trend": r.trend, "bos": r.bos, "choch": r.choch,
          "strong_low": r.strong_low, "strong_high": r.strong_high,
          "hl_confirmed": r.hl_confirmed, "lh_confirmed": r.lh_confirmed,
          "swing_label": r.swing_label} for r in rows],
        index=df.index,
    )
