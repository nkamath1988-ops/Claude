from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from trading_bot.paper_trading.ict_engine import BASE, VARIANTS, advance, format_event, new_state
from trading_bot.strategies.ict_ifvg import find_signals, prepare_rth, simulate

DATA = Path(__file__).resolve().parent.parent / "data_cache_ict" / "SPX_5m.csv"
pytestmark = pytest.mark.skipif(not DATA.exists(), reason="needs cached SPX 5m data")

LO, HI = pd.Timestamp("2025-04-14", tz="UTC"), pd.Timestamp("2025-05-16", tz="UTC")


def _rolling():
    raw = pd.read_csv(DATA, parse_dates=["ts"])
    state, events = new_state(LO.strftime("%Y-%m-%dT%H:%M:%SZ")), []
    for t in pd.date_range(LO, HI, freq="2h"):
        w = raw[(raw.ts > t - pd.Timedelta(days=4.4)) & (raw.ts <= t)]
        if len(w) and prepare_rth(w, 5).date.nunique() >= 3:
            events += advance(state, w)
    return raw, state, events


def test_rolling_runs_reproduce_batch_backtest_and_never_double_report():
    raw, state, events = _rolling()
    full = prepare_rth(raw, 5)
    for name, gap in VARIANTS.items():
        p = replace(BASE, min_gap=gap)
        t = simulate(full, find_signals(full, p), p, "liquidity")
        t = t[(t.entry_time.dt.tz_convert("UTC") > LO) & (t.entry_time.dt.tz_convert("UTC") < HI - pd.Timedelta(days=1))]
        got = [x for x in state["trades"][name] if pd.Timestamp(x["entry_time"]) < HI - pd.Timedelta(days=1)]
        assert [x["pts"] for x in got] == [round(v, 2) for v in t.pts]
    ids = [e["id"] for e in events]
    assert len(ids) == len(set(ids)) and len(ids) > 0
    # re-running on the final window reports nothing new
    w = raw[(raw.ts > HI - pd.Timedelta(days=4.4)) & (raw.ts <= HI)]
    assert advance(state, w) == []


def test_history_before_start_is_not_backfilled_and_short_windows_rejected():
    raw = pd.read_csv(DATA, parse_dates=["ts"])
    w = raw[(raw.ts > HI - pd.Timedelta(days=4.4)) & (raw.ts <= HI)]
    st = new_state(HI.strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert advance(st, w) == [] and st["trades"]["spec9"] == []
    with pytest.raises(ValueError):
        advance(new_state("2025-01-01T00:00:00Z"), raw.iloc[:100])


def test_format_event_fits_a_push_notification():
    ev = dict(type="SIGNAL", variant="spec9", status="pending", side="short", ref_price=7000.12, stop=7021.5,
              target=6960.0, gap=11.2, swept=7005.0)
    assert len(format_event(ev)) < 200 and "SHORT" in format_event(ev)


def test_silent_variants_are_tracked_but_never_reported():
    raw = pd.read_csv(DATA, parse_dates=["ts"])
    lo, hi = pd.Timestamp("2025-05-12", tz="UTC"), pd.Timestamp("2025-06-06", tz="UTC")  # has 15pt AND 9pt trades
    loud, quiet = new_state(lo.strftime("%Y-%m-%dT%H:%M:%SZ")), new_state(lo.strftime("%Y-%m-%dT%H:%M:%SZ"))
    quiet["notify"] = ["gap15"]
    ev_loud, ev_quiet = [], []
    for t in pd.date_range(lo, hi, freq="6h"):
        w = raw[(raw.ts > t - pd.Timedelta(days=4.4)) & (raw.ts <= t)]
        if len(w) and prepare_rth(w, 5).date.nunique() >= 3:
            ev_loud += advance(loud, w)
            ev_quiet += advance(quiet, w)
    assert {e["variant"] for e in ev_loud} == {"spec9", "gap15"}
    assert {e["variant"] for e in ev_quiet} == {"gap15"}                     # still alerts on the chosen variant
    assert [e["id"] for e in ev_quiet] == [e["id"] for e in ev_loud if e["variant"] == "gap15"]
    assert quiet["trades"]["spec9"] == loud["trades"]["spec9"] and quiet["trades"]["spec9"]  # silently logged
