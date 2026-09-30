"""Forward paper trading for the ICT sweep -> delivery -> IFVG -> liquidity-target setup on
SPX 5-minute bars. Places NO orders; it logs what the frozen rules would have done on
real, current data and reports each new signal / paper exit exactly once.

Design: stateless detection, stateful bookkeeping. Each run is given a rolling window of
recent 5-minute bars (>= 3 sessions), replays the same detector and simulator the backtest
uses (`strategies/ict_ifvg.py`), and diffs the result against the JSON state:

* The first session in the window is ignored for signals -- its previous-day pools are
  missing, so any signal there would be unreliable. (The previous run already covered it.)
* Only signals whose bar closed after `start_ts` count, so bootstrapping never back-fills
  history as if it were live.
* A signal on the newest bar has no entry bar yet ("pending": enters at the next 5m open).
* A position that has not hit stop/target and whose session has not finished is "open".
* Every event has a stable id, so re-running on the same data (or overlapping windows)
  never reports twice. `tests/test_ict_paper.py` checks that hourly rolling runs reproduce the
  batch backtest trade-for-trade.

Two variants run side by side, both frozen at creation (`state['notify']` picks which ones raise events; the rest are tracked silently): `spec9` (the 9-point gap that was
asked for) and `gap15` (the exploratory 15-point cut-off, chosen after seeing backtest results,
so it is labelled as such -- only fresh forward trades can validate it).
"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import replace
from pathlib import Path

import pandas as pd

from ..strategies.ict_ifvg import IctParams, find_signals, prepare_rth, simulate

BAR_MINUTES = 5
SESSION_LAST_BAR = "15:55"
BASE = IctParams().scaled(2)            # 10m-validated windows, doubled for 5m bars
VARIANTS = {"spec9": 9.0, "gap15": 15.0}
MIN_SESSIONS = 3


def read_bars(paths: list[str]) -> pd.DataFrame:
    """Real (non-interpolated) 5m bars from Robinhood get_index_historicals tool-result JSON
    files and/or CSVs (ts,open,high,low,close). Interpolated filler is dropped."""
    frames = []
    for p in paths:
        if p.endswith(".csv"):
            d = pd.read_csv(p, parse_dates=["ts"])
        else:
            r = json.load(open(p))["data"]["results"][0]
            rows = [(b["begins_at"], float(b["open_value"]), float(b["high_value"]),
                     float(b["low_value"]), float(b["close_value"]))
                    for b in r["bars"] if not b.get("interpolated")]
            d = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
            d["ts"] = pd.to_datetime(d["ts"], utc=True)
        frames.append(d)
    if not frames:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close"])
    return pd.concat(frames).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def newest_tool_result(pattern: str) -> str | None:
    """Newest 5-minute get_index_historicals tool-result file matching a glob."""
    best = None
    for f in glob.glob(pattern):
        try:
            if json.load(open(f))["data"]["results"][0]["interval"] != "5minute":
                continue
        except Exception:
            continue
        if best is None or os.path.getmtime(f) > os.path.getmtime(best):
            best = f
    return best


def new_state(start_ts: str) -> dict:
    return {"version": 1, "start_ts": start_ts, "bar_minutes": BAR_MINUTES,
            "variants": {k: {"min_gap": v} for k, v in VARIANTS.items()},
            "notify": list(VARIANTS), "last_bar_ts": None, "trades": {k: [] for k in VARIANTS},
            "open": {k: None for k in VARIANTS}, "reported": [], "runs": 0}


def load_state(path: str) -> dict | None:
    return json.load(open(path)) if Path(path).exists() else None


def save_state(state: dict, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(path, "w"), indent=2, sort_keys=True)


def _iso(ts) -> str:
    return pd.Timestamp(ts).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _trade_dict(row, name: str, is_open: bool) -> dict:
    return dict(variant=name, side=row.side, signal_time=_iso(row.entry_time - pd.Timedelta(minutes=BAR_MINUTES)),
                entry_time=_iso(row.entry_time), entry=round(float(row.entry), 2), stop=round(float(row.stop), 2),
                target=round(float(row.target), 2), risk=round(float(row.risk), 2), gap=round(float(row.gap), 2),
                swept=round(float(row.swept), 2), status="open" if is_open else "closed",
                exit_time=None if is_open else _iso(row.exit_time),
                exit=None if is_open else round(float(row.exit), 2),
                exit_reason=None if is_open else row.exit_reason,
                pts=None if is_open else round(float(row.pts), 2), r=None if is_open else round(float(row.r), 3))


def _pending(df: pd.DataFrame, sigs, trades: pd.DataFrame, p: IctParams, start: pd.Timestamp):
    """Signal on the newest bar: would enter at the next 5m open. Only reported if it would
    pass the same gating the simulator applies (no open position, daily cap, risk, target)."""
    n = len(df)
    last = df.iloc[-1]
    out = []
    for s in sigs:
        if s.idx != n - 1 or last["ts"] <= start or df["day"].iat[s.idx] == df["day"].iat[0]:
            continue
        today = trades[trades.entry_time.dt.date == last["date"]] if len(trades) else trades
        if len(today) >= p.max_trades_per_day:
            continue
        if len(today) and today.exit_time.iat[-1] == df["et"].iat[-1] and today.exit_reason.iat[-1] == "eod" \
                and df["hhmm"].iat[-1] < SESSION_LAST_BAR:
            continue  # a position is still open
        close = float(last["close"])
        risk = (close - s.gap_stop) * s.side
        if risk < 1.0 or risk > p.max_risk:
            continue
        cands = [x for x in s.target_pools if (x - close) * s.side >= p.min_rr * risk]
        if not cands:
            continue
        out.append(dict(side="long" if s.side == 1 else "short", signal_time=_iso(last["ts"]),
                        ref_price=round(close, 2), stop=round(s.gap_stop, 2), risk=round(risk, 2),
                        target=round(min(cands) if s.side == 1 else max(cands), 2), gap=round(s.gap_size, 2),
                        swept=round(s.swept_level, 2)))
    return out


def advance(state: dict, bars: pd.DataFrame) -> list[dict]:
    """Replay the detector on `bars`, update `state` in place, return the NEW events
    (not previously reported): SIGNAL (with paper entry if it already happened) and EXIT."""
    df = prepare_rth(bars, BAR_MINUTES)
    if df.empty or df["date"].nunique() < MIN_SESSIONS:
        raise ValueError(f"need >= {MIN_SESSIONS} sessions of real 5m bars, got "
                         f"{0 if df.empty else df['date'].nunique()}")
    start = pd.Timestamp(state["start_ts"])
    first_day = df["day"].iat[0]
    last_et = df["et"].iat[-1]
    reported = set(state["reported"])
    events: list[dict] = []

    notify = set(state.get("notify", VARIANTS))   # silent variants are still tracked, just never reported

    def emit(eid: str, ev: dict) -> None:
        if eid not in reported:
            reported.add(eid)
            if ev["variant"] in notify:
                events.append({"id": eid, **ev})

    for name, gap in VARIANTS.items():
        p = replace(BASE, min_gap=gap)
        sigs = find_signals(df, p)
        trades = simulate(df, sigs, p, "liquidity")
        closed, open_pos = [], None
        for row in trades.itertuples():
            if row.entry_time.tz_convert("UTC") <= start:
                continue
            e_idx = df.index[df["et"] == row.entry_time][0]
            if df["day"].iat[e_idx] == first_day:
                continue
            is_open = (row.exit_reason == "eod" and row.exit_time == last_et
                       and df["hhmm"].iat[-1] < SESSION_LAST_BAR)
            t = _trade_dict(row, name, is_open)
            if is_open:
                open_pos = t
            else:
                closed.append(t)
            emit(f"sig:{name}:{t['signal_time']}", dict(type="SIGNAL", **t))
            if not is_open:
                emit(f"exit:{name}:{t['entry_time']}", dict(type="EXIT", **t))
        for pend in _pending(df, sigs, trades, p, start):
            emit(f"sig:{name}:{pend['signal_time']}", dict(type="SIGNAL", variant=name, status="pending", **pend))
        known = {t["entry_time"]: t for t in state["trades"][name]}
        for t in closed:
            known[t["entry_time"]] = t
        state["trades"][name] = [known[k] for k in sorted(known)]
        state["open"][name] = open_pos

    state["reported"] = sorted(reported)
    state["last_bar_ts"] = _iso(df["ts"].iat[-1])
    state["runs"] += 1
    return events


def summary(state: dict) -> dict:
    out = {}
    for name in VARIANTS:
        ts = state["trades"][name]
        rs = [t["r"] for t in ts]
        out[name] = dict(min_gap=VARIANTS[name], closed=len(ts), open=1 if state["open"][name] else 0,
                         wins=sum(t["pts"] > 0 for t in ts), total_pts=round(sum(t["pts"] for t in ts), 1),
                         avg_r=round(sum(rs) / len(rs), 3) if rs else None)
    return out


def format_event(ev: dict) -> str:
    """One-line human text (<200 chars) suitable for a push notification."""
    v = "9pt" if ev["variant"] == "spec9" else "15pt"
    if ev["type"] == "SIGNAL":
        entry = f"paper entry {ev['entry']}" if ev["status"] != "pending" else f"enter next open, ref {ev['ref_price']}"
        return (f"SPX {ev['side'].upper()} signal [{v}]: {entry}, stop {ev['stop']}, target {ev['target']} "
                f"(gap {ev['gap']}pt, swept {ev['swept']})")
    return (f"SPX paper {ev['side']} [{v}] closed {ev['exit_reason']}: {ev['pts']:+.1f} pts ({ev['r']:+.2f}R), "
            f"exit {ev['exit']}")
