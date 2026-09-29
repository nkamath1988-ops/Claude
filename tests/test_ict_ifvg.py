import numpy as np
import pandas as pd

from trading_bot.strategies.ict_ifvg import IctParams, find_signals, simulate

# bar:      0    1    2    3    4    5    6    7    8    9    10   11   12
O = [105, 106, 105, 101, 102, 105, 107, 105, 93, 91, 95, 110, 111]
H = [108, 108, 107, 103, 106, 108, 108, 105, 94, 96, 112, 118, 120]
L = [100, 100, 100, 95, 100, 101, 104, 92, 90, 90.5, 94, 109, 110]
C = [106, 105, 101, 102, 105, 107, 105, 93, 91, 95, 110, 117, 119]
# bar 3 = swing low 95 (pool, confirmed at bar 5 with swing_len=2); bar 7 sweeps it (low 92);
# bars 6..8 leave a bearish FVG [94, 104] (size 10); bar 10 closes at 110 through the gap top.


def _df(o, h, l, c, n=None):
    n = n or len(o)
    return pd.DataFrame({"open": o[:n], "high": h[:n], "low": l[:n], "close": c[:n],
                         "day": [0] * n, "hhmm": ["10:00"] * n,
                         "et": pd.date_range("2025-01-06 10:00", periods=n, freq="10min", tz="America/New_York")})


P = IctParams(swing_len=2, earliest="00:00", latest="23:59")


def test_long_ifvg_detected_with_expected_levels():
    s = find_signals(_df(O, H, L, C), P)
    assert [(x.idx, x.side) for x in s] == [(10, 1)]
    assert s[0].gap_size == 10 and s[0].sweep_extreme == 90 and s[0].stop == 89 and s[0].gap_stop == 93
    assert s[0].swept_level == 95


def test_short_is_exact_mirror():
    s = find_signals(_df([-x for x in O], [-x for x in L], [-x for x in H], [-x for x in C]), P)
    assert [(x.idx, x.side) for x in s] == [(10, -1)]
    assert s[0].stop == -89 and s[0].gap_stop == -93 and s[0].swept_level == -95


def test_no_lookahead_signal_unchanged_by_future_bars():
    assert [(x.idx) for x in find_signals(_df(O, H, L, C, 11), P)] == [10]
    assert find_signals(_df(O, H, L, C, 10), P) == []


def test_gap_below_minimum_is_ignored():
    h = list(H); h[8] = 96.5  # gap = 104 - 96.5 = 7.5 < 9
    assert find_signals(_df(O, h, L, C), P) == []


def test_close_must_go_through_gap_top():
    c = list(C); c[10] = 103.5  # closes inside the gap: no inversion on bar 10
    assert find_signals(_df(O, H, L, c, 11), P) == []
    # ...and the first close through the top (bar 11) is what triggers, one bar later
    assert [x.idx for x in find_signals(_df(O, H, L, c), P)] == [11]


def _sim(df, mode):
    p = IctParams(swing_len=2, earliest="00:00", latest="23:59", cost_pts=0.0)
    return simulate(df, find_signals(df, p), p, mode)


def test_simulate_enters_next_open_and_exits_on_target():
    t = _sim(_df(O, H, L, C), "rr0.5")  # entry 110, stop 93 (risk 17), target 118.5 hit on bar 12
    assert len(t) == 1 and t.entry.iat[0] == 110 and t.stop.iat[0] == 93
    assert t.exit_reason.iat[0] == "target" and t.exit.iat[0] == 118.5 and abs(t.r.iat[0] - 0.5) < 1e-9


def test_simulate_flat_at_session_end_when_nothing_hit():
    t = _sim(_df(O, H, L, C), "rr1")  # target 127 never reached
    assert t.exit_reason.iat[0] == "eod" and t.exit.iat[0] == C[-1]


def test_simulate_stop_checked_before_target_in_same_bar():
    l = list(L); l[11] = 92  # entry bar trades down through the 93 stop and up through the target
    t = _sim(_df(O, H, l, C), "rr0.5")
    assert t.exit_reason.iat[0] == "stop" and t.exit.iat[0] == 93 and abs(t.r.iat[0] + 1.0) < 1e-9


def test_load_rth_is_timeframe_aware_and_drops_flat_prints(tmp_path):
    from trading_bot.strategies.ict_ifvg import load_rth
    # 2025-01-06 (EST): RTH = 14:30Z..20:55Z start times for 5m bars; 21:00Z is the flat post-close print
    ts = pd.date_range("2025-01-06 14:25", "2025-01-06 21:05", freq="5min", tz="UTC")
    px = np.arange(len(ts), dtype=float) + 5000
    df = pd.DataFrame({"ts": ts, "open": px, "high": px + 1, "low": px - 1, "close": px + 0.5})
    df.loc[df.ts == pd.Timestamp("2025-01-06 21:00", tz="UTC"), ["open", "high", "low", "close"]] = 5100.0  # flat
    p = tmp_path / "x.csv"; df.to_csv(p, index=False)
    b5, b10 = load_rth(str(p), 5), load_rth(str(p), 10)
    assert b5.hhmm.iloc[0] == "09:30" and b5.hhmm.iloc[-1] == "15:55" and len(b5) == 78
    assert b10.hhmm.iloc[-1] == "15:50"
    assert IctParams().scaled(2).swing_len == 10 and IctParams().scaled(2).sweep_window == 24
