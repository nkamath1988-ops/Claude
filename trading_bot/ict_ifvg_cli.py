"""Backtest the ICT "sweep -> delivery -> inverse FVG -> liquidity target" setup on
SPX 10-minute regular-hours bars (data_cache_ict/SPX_10m.csv).

Prints the primary run, then the checks that decide whether the result means anything:
a bootstrap CI on mean R, a random-entry control (same side / risk / target distance,
random timing), a gap-size sensitivity table, a stop-definition comparison and a
year-by-year split. Parameters are fixed up front (not fitted); the sensitivity
tables are there to expose fragility, not to pick a winner.

Example:
    python -m trading_bot.ict_ifvg_cli
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .strategies.ict_ifvg import IctParams, Signal, find_signals, load_rth, simulate, walk_trade


def stats(t: pd.DataFrame) -> dict:
    if t.empty:
        return dict(n=0)
    w, lo = t.pts[t.pts > 0].sum(), -t.pts[t.pts <= 0].sum()
    eq = t.pts.cumsum()
    streak = best = 0
    for v in t.pts <= 0:
        streak = streak + 1 if v else 0
        best = max(best, streak)
    return dict(n=len(t), win=(t.pts > 0).mean(), avg_r=t.r.mean(), med_r=t.r.median(),
                pf=(w / lo) if lo > 0 else np.inf, total_pts=t.pts.sum(), avg_pts=t.pts.mean(),
                max_dd_pts=(eq.cummax() - eq).max(), max_lose_streak=best,
                tgt=(t.exit_reason == "target").mean(), stp=(t.exit_reason == "stop").mean())


def fmt(s: dict) -> str:
    if s["n"] == 0:
        return "n=0"
    return (f"n={s['n']:>3} win={s['win']:.0%} avgR={s['avg_r']:+.3f} medR={s['med_r']:+.2f} "
            f"PF={s['pf']:.2f} pts={s['total_pts']:+.0f} avg={s['avg_pts']:+.1f} "
            f"maxDD={s['max_dd_pts']:.0f} losestreak={s['max_lose_streak']} "
            f"tgt/stop/eod={s['tgt']:.0%}/{s['stp']:.0%}/{1 - s['tgt'] - s['stp']:.0%}")


def bootstrap_ci(x: np.ndarray, n=10_000, seed=0):
    rng = np.random.default_rng(seed)
    m = rng.choice(x, (n, len(x))).mean(axis=1)
    return np.percentile(m, [2.5, 97.5]), (m <= 0).mean()


def random_entry_control(df: pd.DataFrame, trades: pd.DataFrame, p: IctParams, draws=2000, seed=1):
    """Keep each real trade's side, risk and target distance; move the entry to a random
    in-window bar. Returns the distribution of mean R. If the real mean R sits inside it,
    the IFVG timing adds nothing over 'any entry with this stop/target geometry'."""
    o, h, l, c = (df[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    day, hhmm = df["day"].to_numpy(), df["hhmm"].to_numpy()
    valid = np.array([i for i in range(len(df) - 1) if p.earliest <= hhmm[i] <= p.latest and day[i + 1] == day[i]])
    side = np.where(trades.side == "long", 1, -1)
    risk, tdist = trades.risk.to_numpy(), ((trades.target - trades.entry).abs()).to_numpy()
    rng = np.random.default_rng(seed)
    out = np.empty(draws)
    for d in range(draws):
        rs = []
        for k in range(len(trades)):
            e = int(rng.choice(valid)) + 1
            stop = o[e] - side[k] * risk[k]
            tgt = o[e] + side[k] * tdist[k]
            _, px, _ = walk_trade(o, h, l, c, day, e, side[k], stop, tgt)
            rs.append(((px - o[e]) * side[k] - p.cost_pts) / risk[k])
        out[d] = np.mean(rs)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data_cache_ict/SPX_10m.csv")
    ap.add_argument("--out-dir", default="reports_out_ict")
    ap.add_argument("--draws", type=int, default=2000)
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(exist_ok=True)

    df = load_rth(a.data)
    print(f"SPX 10m RTH bars: {len(df)}  sessions: {df.date.nunique()}  {df.date.min()} -> {df.date.max()}\n")

    p = IctParams()
    sigs = find_signals(df, p)
    print(f"PRIMARY  min_gap={p.min_gap} swing_len={p.swing_len} stop=beyond inverted gap "
          f"max_risk={p.max_risk} target=nearest opposing liquidity (>= {p.min_rr}R) cost={p.cost_pts}pt")
    print(f"raw signals: {len(sigs)}  ({sum(s.side == 1 for s in sigs)} long / {sum(s.side == -1 for s in sigs)} short)")
    t = simulate(df, sigs, p, "liquidity")
    t.to_csv(out / "primary_trades.csv", index=False)
    print("ALL   ", fmt(stats(t)))
    for sd in ("long", "short"):
        print(f"{sd:<6}", fmt(stats(t[t.side == sd])))
    t["year_half"] = pd.to_datetime(t.entry_time, utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-Q") + pd.to_datetime(t.entry_time, utc=True).dt.tz_convert("America/New_York").dt.quarter.astype(str)
    print("\nBy quarter:")
    for q, g in t.groupby("year_half"):
        print(f"  {q}", fmt(stats(g)))
    first, second = t[pd.to_datetime(t.entry_time, utc=True) < pd.Timestamp("2025-10-01", tz="UTC")], \
        t[pd.to_datetime(t.entry_time, utc=True) >= pd.Timestamp("2025-10-01", tz="UTC")]
    print("\nYear 1 (Oct24-Sep25):", fmt(stats(first)))
    print("Year 2 (Oct25-Sep26):", fmt(stats(second)))

    if len(t) >= 5:
        (lo, hi), p0 = bootstrap_ci(t.r.to_numpy())
        print(f"\nBootstrap 95% CI on mean R: [{lo:+.3f}, {hi:+.3f}]   P(mean R <= 0) = {p0:.1%}")
        ctl = random_entry_control(df, t, p, a.draws)
        print(f"Random-entry control (same side/risk/target dist, random timing, {a.draws} draws): "
              f"mean R = {ctl.mean():+.3f} (sd {ctl.std():.3f}); real {t.r.mean():+.3f} beats "
              f"{(ctl < t.r.mean()).mean():.1%} of draws  -> p ~ {(ctl >= t.r.mean()).mean():.3f}")

    print("\nTarget-mode comparison (same signals, same stop):")
    for m in ("liquidity", "rr1", "rr2", "rr3"):
        print(f"  {m:<9}", fmt(stats(simulate(df, sigs, p, m))))

    print("\nStop definition:")
    for sm, mr in (("gap", 30.0), ("gap", 150.0), ("sweep", 150.0)):
        q = IctParams(stop_mode=sm, max_risk=mr)
        print(f"  stop={sm:<5} max_risk={mr:>5.0f} liquidity:", fmt(stats(simulate(df, find_signals(df, q), q, "liquidity"))))

    print("\nSensitivity to minimum FVG size (liquidity target, gap stop):")
    for g in (3, 5, 7, 9, 12, 15):
        q = IctParams(min_gap=float(g))
        s2 = find_signals(df, q)
        print(f"  min_gap={g:>2} signals={len(s2):>3}", fmt(stats(simulate(df, s2, q, "liquidity"))))
    print("\nSensitivity to swing length (pool definition):")
    for k in (3, 5, 8):
        q = IctParams(swing_len=k)
        s2 = find_signals(df, q)
        print(f"  swing_len={k} signals={len(s2):>3}", fmt(stats(simulate(df, s2, q, "liquidity"))))
    print("\nCost sensitivity (round-trip points):")
    for cst in (0.0, 0.5, 1.0, 2.0):
        q = IctParams(cost_pts=cst)
        print(f"  cost={cst:<4}", fmt(stats(simulate(df, find_signals(df, q), q, "liquidity"))))


if __name__ == "__main__":
    main()
