#!/usr/bin/env python3
"""Daily simulated paper trade: Hull (EHMA) + Donchian trend, SPY & QQQ, 1-minute bars.

Rules (fixed, see README.md): long when Donchian line is green AND Hull is green, short when both red.
Exit on Hull colour flip, 3 ATR stop, 1.5 ATR take-profit, flat at the end of each session.
Fills are simulated from that day's 1-minute bars; this is NOT a broker paper account.
"""
import json, os, subprocess, sys, time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TRADES = os.path.join(HERE, "trades.csv")
SESSIONS = os.path.join(HERE, "sessions.csv")
SYMS = ["SPY", "QQQ"]
P = dict(hull_len=70, don_len=20, atr_len=14, stop_atr=3.0, tp_atr=1.5, cost_per_side=0.01)
START_DATE = os.environ.get("PAPER_START", "2026-10-05")
MAX_SESSIONS = 21   # the test ends after this many completed sessions per symbol
WARMUP_DAYS = int(os.environ.get("PAPER_WARMUP_DAYS", "2"))
OFFLINE = os.environ.get("PAPER_OFFLINE_DIR")

def fetch(sym):
    if OFFLINE:
        return json.load(open(os.path.join(OFFLINE, f"{sym}_1mL.json")))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range=8d"
    for k in range(5):
        out = subprocess.run(["curl", "-sS", "-m", "30", "-A", "Mozilla/5.0", url], capture_output=True, text=True).stdout
        try:
            d = json.loads(out)
            if d["chart"]["result"]:
                return d
        except Exception:
            pass
        time.sleep(3 * (k + 1))
    raise RuntimeError(f"could not download {sym}")

def load(sym):
    r = fetch(sym)["chart"]["result"][0]; q = r["indicators"]["quote"][0]
    idx = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert("America/New_York")
    df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}, index=idx).dropna()
    return df[~df.index.duplicated()].between_time("09:30", "15:59")

def ehma(src, n):
    e = lambda x, l: x.ewm(span=l, adjust=False).mean()
    return e(2 * e(src, n // 2) - e(src, n), int(round(np.sqrt(n))))

def atr(df, n):
    c = df.c; tr = pd.concat([df.h - df.l, (df.h - c.shift()).abs(), (df.l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean().values

def signals(df):
    c = df.c; H = ehma(c, P["hull_len"]); up = (H > H.shift(2)).values; dn = (H < H.shift(2)).values
    hh = df.h.rolling(P["don_len"]).max().values; ll = df.l.rolling(P["don_len"]).min().values
    cv = c.values; tr = np.zeros(len(df)); cur = 0
    for i in range(1, len(df)):
        if cv[i] > hh[i - 1]: cur = 1
        elif cv[i] < ll[i - 1]: cur = -1
        tr[i] = cur
    trp = np.r_[0, tr[:-1]]
    return (tr == 1) & (trp == 1) & up, (tr == -1) & (trp == -1) & dn, up, dn   # long, short, hull_up, hull_dn

def simulate(df):
    O = df.o.values; H = df.h.values; Lw = df.l.values; C = df.c.values; idx = df.index; day = idx.date
    A = atr(df, P["atr_len"]); L, S, hu, hd = signals(df)
    st = dict(pos=0, ent=0.0, ent_i=0, stop=0.0, tp=0.0, blocked=False); out = []
    def close(i, px, why):
        out.append(dict(side=st["pos"], entry_time=idx[st["ent_i"]], exit_time=idx[i], entry=st["ent"], exit=px, reason=why))
        st["pos"] = 0; st["blocked"] = why in ("stop", "tp")
    for i in range(1, len(C)):
        nd = day[i] != day[i - 1]
        if nd and st["pos"] != 0: close(i - 1, C[i - 1], "eod")
        if nd: st["blocked"] = False; continue            # no decisions across the overnight gap
        if st["blocked"] and not (L[i - 1] or S[i - 1]): st["blocked"] = False
        pos = st["pos"]
        if pos != 0:                                        # gaps through stop / target at the open
            if (pos == 1 and O[i] <= st["stop"]) or (pos == -1 and O[i] >= st["stop"]): close(i, O[i], "stop")
            elif (pos == 1 and O[i] >= st["tp"]) or (pos == -1 and O[i] <= st["tp"]): close(i, O[i], "tp")
        pos = st["pos"]; want = pos
        if pos == 1 and hd[i - 1]: want = -1 if S[i - 1] else 0
        elif pos == -1 and hu[i - 1]: want = 1 if L[i - 1] else 0
        elif pos == 0 and not st["blocked"]: want = 1 if L[i - 1] else (-1 if S[i - 1] else 0)
        if want != pos:
            if pos != 0: close(i, O[i], "hull_flip")
            st["pos"] = want
            if want:
                st["ent"] = O[i]; st["ent_i"] = i
                st["stop"] = O[i] - want * P["stop_atr"] * A[i - 1]; st["tp"] = O[i] + want * P["tp_atr"] * A[i - 1]
        pos = st["pos"]
        if pos != 0:                                        # stop first if both inside the same bar (conservative)
            hit_s = (pos == 1 and Lw[i] <= st["stop"]) or (pos == -1 and H[i] >= st["stop"])
            hit_t = (pos == 1 and H[i] >= st["tp"]) or (pos == -1 and Lw[i] <= st["tp"])
            if hit_s: close(i, st["stop"], "stop")
            elif hit_t: close(i, st["tp"], "tp")
    if st["pos"] != 0: close(len(C) - 1, C[-1], "eod")
    return out

def complete_days(df):
    days = []
    for d, g in df.groupby(df.index.date):
        if g.index[-1].strftime("%H:%M") >= "15:55" and len(g) >= 300: days.append(d)
    return days

def run_symbol(sym):
    df = load(sym); days = complete_days(df)
    df = df[np.isin(df.index.date, days)]
    done = set()
    if os.path.exists(SESSIONS):
        s = pd.read_csv(SESSIONS); done = set(zip(s.date.astype(str), s.symbol))
    room = MAX_SESSIONS - sum(1 for d, y in done if y == sym)
    new_days = [str(d) for k, d in enumerate(days) if k >= WARMUP_DAYS and str(d) >= START_DATE and (str(d), sym) not in done][:max(room, 0)]
    if not new_days: return [], []
    trades = [t for t in simulate(df) if str(t["exit_time"].date()) in new_days]
    rows = []
    for t in trades:
        gross = t["side"] * (t["exit"] - t["entry"]) / t["entry"] * 1e4
        net = gross - 2 * P["cost_per_side"] / t["entry"] * 1e4
        rows.append(dict(date=str(t["exit_time"].date()), symbol=sym, side="long" if t["side"] == 1 else "short",
            entry_time=t["entry_time"].strftime("%H:%M"), exit_time=t["exit_time"].strftime("%H:%M"),
            entry=round(t["entry"], 3), exit=round(t["exit"], 3), reason=t["reason"], gross_bp=round(gross, 2), net_bp=round(net, 2)))
    return rows, new_days

def append(path, df):
    df.to_csv(path, mode="a", header=not os.path.exists(path), index=False)

def stats(sub):
    r = sub.net_bp.values; n = len(r)
    if n < 3: return None
    w = r[r > 0]; l = r[r <= 0]; se = r.std(ddof=1) / np.sqrt(n); m = r.mean()
    eq = np.cumprod(1 + r / 1e4); dd = (eq / np.maximum.accumulate(eq) - 1).min() * 100
    return dict(n=n, win=100 * (r > 0).mean(), avg_win=w.mean() if len(w) else 0, avg_loss=l.mean() if len(l) else 0,
        exp=m, se=se, lo=m - 1.96 * se, hi=m + 1.96 * se, t=m / se if se > 0 else np.nan,
        pf=w.sum() / max(1e-9, -l.sum()), dd=dd)

def main():
    new_t = []; new_s = []
    for sym in SYMS:
        rows, days = run_symbol(sym)
        new_t += rows; new_s += [dict(date=d, symbol=sym) for d in days]
    if new_t: append(TRADES, pd.DataFrame(new_t))
    if new_s: append(SESSIONS, pd.DataFrame(new_s))
    out = []
    if not new_s: out.append("No new completed session to process (market closed / holiday / already logged).")
    else:
        for d in sorted({x["date"] for x in new_s}):
            out.append(f"=== Session {d} ===")
            for sym in SYMS:
                day = [t for t in new_t if t["date"] == d and t["symbol"] == sym]
                if not any(x["date"] == d and x["symbol"] == sym for x in new_s): continue
                if not day: out.append(f"{sym}: no trades"); continue
                net = sum(t["net_bp"] for t in day); wins = sum(t["net_bp"] > 0 for t in day)
                out.append(f"{sym}: {len(day)} trades, {wins} winners, net {net:+.1f} bp (sum of trades)")
                for t in day: out.append(f"   {t['side']:5s} {t['entry_time']}->{t['exit_time']} {t['entry']}->{t['exit']} {t['reason']:9s} {t['net_bp']:+.1f}bp")
    if os.path.exists(TRADES):
        tr = pd.read_csv(TRADES); ss = pd.read_csv(SESSIONS)
        out.append("\n=== CUMULATIVE (net of $0.01/share/side) ===")
        for sym in SYMS:
            nd = ss[ss.symbol == sym].date.nunique(); s = stats(tr[tr.symbol == sym])
            if not s: out.append(f"{sym}: {nd} sessions, too few trades"); continue
            out.append(f"{sym}: {nd} sessions, {s['n']} trades | win {s['win']:.0f}% avg win {s['avg_win']:+.1f}bp avg loss {s['avg_loss']:+.1f}bp "
                       f"| expectancy {s['exp']:+.2f}bp (95% CI {s['lo']:+.2f} to {s['hi']:+.2f}, t={s['t']:.2f}) | PF {s['pf']:.2f} | maxDD {s['dd']:.1f}%")
    if os.path.exists(SESSIONS):
        ss = pd.read_csv(SESSIONS)
        if all(ss[ss.symbol == y].date.nunique() >= MAX_SESSIONS for y in SYMS):
            out.append(f"\nTEST COMPLETE: {MAX_SESSIONS} sessions logged for every symbol. Write the final verdict against README.md.")
    text = "\n".join(out); print(text)
    open(os.path.join(HERE, "report_latest.txt"), "w").write(text + "\n")

if __name__ == "__main__":
    main()
