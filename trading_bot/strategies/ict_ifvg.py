"""ICT-style "liquidity sweep -> delivery -> inverse FVG -> liquidity target" setup,
detected bar-by-bar on intraday index bars with no lookahead.

Definitions (the user gave the concept names only, so these are this module's
explicit, testable interpretation -- change them here, not in the CLI):

* **Liquidity pool** -- resting stops the market is likely to run: the previous
  session's high/low, plus any *unswept* fractal swing high/low (a bar whose
  high/low is strictly beyond the `swing_len` bars on each side; it only becomes
  a pool `swing_len` bars later, when it can first be confirmed).
* **Sweep** -- a bar trades through a pool (low < sell-side pool for a long setup).
* **Fair value gap (FVG)** -- 3-bar imbalance. Bearish FVG: high[g] < low[g-2];
  gap = [high[g], low[g-2]]. Only gaps of at least `min_gap` index points count.
* **Inverse FVG (IFVG)** -- a bearish FVG that formed in the down-leg into the
  sweep low and is then *closed through* (a bar closes above its top) for the
  first time. That flips the gap's polarity, so it is the long trigger.
* **Delivery** -- the inverting bar must be a displacement bar (body >=
  `disp_body_frac` of range and range >= `disp_range_mult` x the mean range of
  the prior 20 bars) *and* must close back above the swept pool (a reclaim).
* **Target** -- the nearest unswept opposing liquidity pool at least `min_rr` x
  risk away (previous-day extreme, session extreme or unswept swing).
* **Stop** -- `stop_mode="gap"`: just beyond the far edge of the inverted gap (the
  usual IFVG invalidation); `stop_mode="sweep"`: beyond the sweep extreme.

Shorts are the exact mirror and are produced by negating prices (open,high,low,
close -> -open,-low,-high,-close) and reusing the long-side detector.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

RTH_START = "09:30"


@dataclass
class IctParams:
    min_gap: float = 9.0
    swing_len: int = 5
    sweep_window: int = 12       # bars allowed between sweep low and the inversion
    gap_lookback: int = 15       # FVG may form up to this many bars before the sweep began
    disp_body_frac: float = 0.5
    disp_range_mult: float = 1.0
    stop_buffer: float = 1.0
    stop_mode: str = "gap"        # "gap" or "sweep"
    max_risk: float = 30.0
    min_rr: float = 1.0
    cost_pts: float = 0.5        # round-trip slippage + commission, index points
    earliest: str = "09:50"      # no entries before this ET bar-start
    latest: str = "15:00"        # no entries after this ET bar-start
    max_trades_per_day: int = 2
    disp_lookback: int = 20      # bars in the average-range baseline for displacement

    def scaled(self, k: int) -> "IctParams":
        """Same clock-time behaviour on bars k times shorter (bar-count params x k)."""
        from dataclasses import replace
        return replace(self, swing_len=self.swing_len * k, sweep_window=self.sweep_window * k,
                       gap_lookback=self.gap_lookback * k, disp_lookback=self.disp_lookback * k)


@dataclass
class Signal:
    idx: int                     # bar whose close confirmed the IFVG (entry = next open)
    side: int                    # +1 long / -1 short
    stop: float
    gap_size: float
    swept_level: float
    sweep_extreme: float
    gap_stop: float = 0.0        # stop beyond the inverted gap's far edge
    target_pools: list = field(default_factory=list)  # opposing pool levels known at idx (original price space)


def load_rth(path: str, bar_minutes: int = 10) -> pd.DataFrame:
    """Read a cached intraday CSV, convert to US/Eastern, keep regular-hours bars only
    (last bar starts at 16:00 - bar_minutes) and drop flat o=h=l=c prints (post-close /
    early-close filler). Adds `day` (session ordinal), `date` and `hhmm`."""
    return prepare_rth(pd.read_csv(path, parse_dates=["ts"]), bar_minutes)


def prepare_rth(df: pd.DataFrame, bar_minutes: int = 10) -> pd.DataFrame:
    """DataFrame form of `load_rth` (columns ts[UTC], open, high, low, close)."""
    df = df.drop_duplicates("ts").sort_values("ts").copy()
    df["et"] = df["ts"].dt.tz_convert("America/New_York")
    df["hhmm"] = df["et"].dt.strftime("%H:%M")
    last = f"{(960 - bar_minutes) // 60:02d}:{(960 - bar_minutes) % 60:02d}"
    flat = (df.open == df.high) & (df.high == df.low) & (df.low == df.close)
    df = df[(df.hhmm >= RTH_START) & (df.hhmm <= last) & ~flat].copy()
    df["date"] = df["et"].dt.date
    df["day"] = df["date"].rank(method="dense").astype(int) - 1
    return df.reset_index(drop=True)


def _fractal_high(h: np.ndarray, j: int, k: int) -> bool:
    if j < k or j + k >= len(h):
        return False
    return h[j] > h[j - k:j].max() and h[j] > h[j + 1:j + k + 1].max()


def _fractal_low(l: np.ndarray, j: int, k: int) -> bool:
    if j < k or j + k >= len(l):
        return False
    return l[j] < l[j - k:j].min() and l[j] < l[j + 1:j + k + 1].min()


def _long_signals(o, h, l, c, day, hhmm, p: IctParams) -> list[Signal]:
    """Long-side detector. Everything at bar b uses data up to and including b only."""
    n = len(c)
    rng = h - l
    pools_lo: list[list] = []   # [level, day_formed]
    pools_hi: list[list] = []
    session_hi = session_lo = None
    active = None               # current sweep state
    out: list[Signal] = []
    k = p.swing_len

    for b in range(n):
        d = day[b]
        new_day = b == 0 or day[b] != day[b - 1]
        if new_day:
            if b > 0:
                prev = day == d - 1
                pools_hi.append([h[prev].max(), d - 1])
                pools_lo.append([l[prev].min(), d - 1])
            session_hi, session_lo = h[b], l[b]
            active = None
        else:
            session_hi, session_lo = max(session_hi, h[b]), min(session_lo, l[b])

        # bar-b sweeps of sell-side pools formed before b
        swept_now = [pl for pl in pools_lo if l[b] < pl[0]]
        if swept_now:
            pools_lo = [pl for pl in pools_lo if l[b] >= pl[0]]
            lvl = max(pl[0] for pl in swept_now)
            if active is None:
                active = {"start": b, "low": l[b], "low_bar": b, "level": lvl}
            else:
                active["level"] = max(active["level"], lvl)
                if l[b] < active["low"]:
                    active["low"], active["low_bar"] = l[b], b
        elif active is not None and l[b] < active["low"]:
            active["low"], active["low_bar"] = l[b], b
        pools_hi = [ph for ph in pools_hi if h[b] <= ph[0]]

        # IFVG trigger (must come strictly after the sweep low bar)
        if active is not None:
            if b - active["low_bar"] > p.sweep_window:
                active = None
            elif b > active["low_bar"] and hhmm[b] >= p.earliest and hhmm[b] <= p.latest:
                best = None
                for g in range(max(2, active["start"] - p.gap_lookback), active["low_bar"] + 1):
                    if day[g] != d:
                        continue
                    top, bot = l[g - 2], h[g]
                    size = top - bot
                    if size < p.min_gap:
                        continue
                    if b > g + 1 and c[g + 1:b].max() > top:
                        continue  # already inverted earlier
                    if c[b] > top and (best is None or size > best[0]):
                        best = (size, top, h[g])
                if best is not None:
                    prior = rng[max(0, b - p.disp_lookback):b]
                    body = abs(c[b] - o[b])
                    disp = (rng[b] > 0 and body / rng[b] >= p.disp_body_frac
                            and rng[b] >= p.disp_range_mult * prior.mean())
                    if disp and c[b] > active["level"]:
                        targets = sorted([ph[0] for ph in pools_hi] + [session_hi])
                        out.append(Signal(b, 1, active["low"] - p.stop_buffer, best[0],
                                          active["level"], active["low"], best[2] - p.stop_buffer, targets))
                        active = None

        # register swing pools that become confirmed at bar b (swing at b-k)
        j = b - k
        if j >= 0 and day[j] == d:
            if _fractal_high(h, j, k):
                pools_hi.append([h[j], d])
            if _fractal_low(l, j, k):
                pools_lo.append([l[j], d])
        # expire old pools (keep current + previous session)
        pools_hi = [x for x in pools_hi if x[1] >= d - 1]
        pools_lo = [x for x in pools_lo if x[1] >= d - 1]
    return out


def find_signals(df: pd.DataFrame, p: IctParams) -> list[Signal]:
    o, h, l, c = (df[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    day, hhmm = df["day"].to_numpy(), df["hhmm"].to_numpy()
    longs = _long_signals(o, h, l, c, day, hhmm, p)
    shorts = _long_signals(-o, -l, -h, -c, day, hhmm, p)
    for s in shorts:  # map back to original price space
        s.side = -1
        s.stop = -s.stop
        s.swept_level = -s.swept_level
        s.sweep_extreme = -s.sweep_extreme
        s.gap_stop = -s.gap_stop
        s.target_pools = sorted(-x for x in s.target_pools)
    return sorted(longs + shorts, key=lambda s: s.idx)


def walk_trade(o, h, l, c, day, e: int, side: int, stop: float, tgt: float):
    """Walk one trade from entry bar `e` (filled at its open). Stop is checked before
    target inside a bar (conservative); a gap through the stop fills at the open.
    Flat at the session's last bar close. Returns (last_bar, exit_price, reason)."""
    n = len(c)
    x = e
    while True:
        if side == 1:
            if l[x] <= stop:
                return x, (min(o[x], stop) if x > e else stop), "stop"
            if h[x] >= tgt:
                return x, tgt, "target"
        else:
            if h[x] >= stop:
                return x, (max(o[x], stop) if x > e else stop), "stop"
            if l[x] <= tgt:
                return x, tgt, "target"
        if x + 1 >= n or day[x + 1] != day[e]:
            return x, c[x], "eod"
        x += 1


def simulate(df: pd.DataFrame, signals: list[Signal], p: IctParams, target_mode: str = "liquidity") -> pd.DataFrame:
    """Walk signals chronologically; one position at a time, `max_trades_per_day`.
    Entry = next bar open. Stop is checked before target within a bar (conservative).
    Flat at the last bar of the session. target_mode: 'liquidity' or 'rr<x>' (fixed R)."""
    o, h, l, c = (df[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    day = df["day"].to_numpy()
    n = len(df)
    trades, busy_until, per_day = [], -1, {}
    for s in signals:
        e = s.idx + 1
        if e >= n or day[e] != day[s.idx] or e <= busy_until:
            continue
        if per_day.get(day[e], 0) >= p.max_trades_per_day:
            continue
        entry = o[e]
        stop = s.gap_stop if p.stop_mode == "gap" else s.stop
        risk = (entry - stop) * s.side
        if risk < 1.0 or risk > p.max_risk:
            continue
        if target_mode == "liquidity":
            if s.side == 1:
                cands = [x for x in s.target_pools if x - entry >= p.min_rr * risk]
                tgt = min(cands) if cands else None
            else:
                cands = [x for x in s.target_pools if entry - x >= p.min_rr * risk]
                tgt = max(cands) if cands else None
            if tgt is None:
                continue
        else:
            tgt = entry + s.side * float(target_mode[2:]) * risk
        x, exit_px, reason = walk_trade(o, h, l, c, day, e, s.side, stop, tgt)
        pts = (exit_px - entry) * s.side - p.cost_pts
        trades.append(dict(entry_time=df["et"].iat[e], exit_time=df["et"].iat[x], side="long" if s.side == 1 else "short",
                           entry=entry, stop=stop, target=tgt, exit=exit_px, exit_reason=reason,
                           bars_held=x - e + 1, risk=risk, gap=s.gap_size, pts=pts, r=pts / risk,
                           swept=s.swept_level))
        busy_until = x
        per_day[day[e]] = per_day.get(day[e], 0) + 1
    return pd.DataFrame(trades)
