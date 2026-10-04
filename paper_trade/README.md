# Paper trade: Hull (EHMA 70) + Donchian (20) 1-minute scalp on SPY and QQQ

Started with the first full session on or after 2026-10-05. One run per weekday after the close.
The paper trade is a **simulation** on that day's 1-minute bars. It is not a broker paper account.

## Rules (fixed, do not change during the test)
- Long when the Donchian line is green AND the Hull (EHMA 70, close vs 2 bars ago) is green. Short when both are red.
- No decisions across the overnight gap. Flat at the end of each session. Entries and exits at the next bar's open.
- Exit on Hull colour flip (reverse if the other side is also aligned), 1.5 ATR(14) take-profit, and a 3 ATR stop.
- **Stop-loss switch (user decision, made before the test):** the official paper account uses the 3 ATR stop for sessions 1-15 and **no stop from session 16 on**.
  To keep the test valid, the runner simulates BOTH versions (`stop3` and `nostop`) on every session and logs them in the `variant` column,
  so each version has its own full 21-session sample and the switch is judged on data, not on a mid-test rule change.
- After a stop or target, wait until the signal alignment resets before re-entering.
- If a bar reaches both the stop and the target, the stop is counted (conservative).
- Cost: $0.01 per share per side on every trade (spread/slippage allowance), no commission.

## Pass criteria (set before the test, per symbol, applied to `stop3`, `nostop` and the official mixed account)
- At least 21 completed sessions AND about 250 trades. The runner stops logging after 21 sessions per symbol.
- Average net P&L per trade (bp) > 0 with the lower end of the 95% CI (mean +/- 1.96 SE) above 0.
- Profit factor >= 1.2.
- If the CI straddles zero the result is **inconclusive, not a pass**. Win rate alone is not a criterion:
  the setup needs about a 57-59% win rate to break even and won about 50% in the backtest.

## Files
- `paper.py`: runner. `trades.csv`: every simulated trade. `sessions.csv`: sessions processed. `report_latest.txt`: last report.
- The backtest sample (11 Sep to 2 Oct 2026) is in-sample and is NOT in the log.

## Note on the stop-loss switch
In the 16-day backtest the two versions were nearly identical (SPY -0.96 vs -0.89 bp per trade, QQQ -1.46 vs -1.57 bp), but
without a stop the worst QQQ trade was -59 bp against -46 bp with it. The paper test will show whether that difference matters.
