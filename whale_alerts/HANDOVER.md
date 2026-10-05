# Whale-alert options: analysis handover

Source: Discord channel `#whale-trades`, bot "SPX Plays - Whale Alerts Bot". Every alert so far is a single-leg
BUY of a call (no puts, sells, spreads, or sizes). The 16 alerts analysed are in `alerts_log.csv`.
Analysis done 2026-10-04 (a Sunday) with Robinhood 30-minute stock bars and quotes.

## Goal
Work out what strategy the "whales" appear to be using and whether it can be copied. Plan agreed with the user:
paste each new alert (with its Discord timestamp) into a session, decipher the likely strategy, then paper trade it.

## Conclusions so far
1. **No single identifiable strategy.** The alerts split into setups that contradict each other:
   - ATM or near-ATM 0DTE dip buys (AMD, INTC x2, TSLA 347.5c, AAPL): 1 of 5 won.
   - Momentum chases after an opening spike (MSFT, META 800c, ORCL): 1 of 3 won (and the ORCL entry is suspect, see below).
   - Mildly OTM calls held 1-4 days (GOOGL x3, GS, META 750c): 0 of 5 paid at expiry.
   - MU (bought 3:21pm ET before an overnight move) and TLT (two-month rates-reversal bet) fit neither.
2. **Results at expiry (14 expired):** 2 winners (TSLA 347.5c +285%, ORCL 135c +204%), 2 mostly lost (INTC 116c -96%, INTC 120c -67%), 10 went to zero.
   Average about -48% equal-dollar, about -36% premium-weighted. Counting the live TSLA 365c at intrinsic only: about -22% premium-weighted.
   Two contracts still live at last check: TSLA 365c 10/9 (spot 370.70) and TLT 83c 11/30 (spot 77.49).
3. **Exit timing decided outcomes.** GOOGL 345c, GOOGL 350c and the TSLA calls were in the money intraday before expiry. Only about 5 of 16 were ever ITM after the alert.
   The feed gives no exit alerts, so the whale's real P&L is unknown.
4. **No cheap-volatility edge.** Implied vol backed out of the entry prices is roughly 21-33% on the mega-caps, i.e. normal market pricing.
5. **Alert prices may be stale.** ORCL 135c "Entry $2.40" only fits spot of about 133.5 (the 9:30 ET open). By the 7:04 PT alert ORCL was about 141,
   where that call would cost $6+. That implies the alert lagged the fill by about 30 minutes. One clear case, not proof it is typical.
6. **Selection caveats.** Only calls and only BUYs appear, so the feed may show only bullish prints. A large call buy can be a spread leg or hedge.
   The channel is a promotional alerts bot, so check whether its record is audited.

## Assumptions and open items
- **Timezone:** the Discord timestamps are read as US Pacific (ET = PT + 3h). Read as ET, 12 of 16 alerts fall pre-market, when options don't trade. Confirm the user's phone is on Pacific time.
- Spot at alert is approximated from the 30-minute bar containing the alert. For 0DTE fills a 1-minute view would be better.
- Historical option quotes for the expired contracts were not pulled. Entry-price checks used a Black-Scholes implied-vol back-out, not real chain data.
- Earlier chat message corrected itself: there were 12 alerts in the first paste, 16 once the screenshots added earlier ones (META 800c, GOOGL 347.5c, MSFT, AAPL).
- Tesla deliveries around Oct 2 as the reason for the 55M-share volume spike is unverified.

## Paper-trading protocol (to follow for each new alert)
1. Record the alert text, Discord timestamp and timezone as soon as it arrives. Late logging makes the paper fill guesswork.
2. Within 1-2 minutes, pull the option bid/ask (Robinhood `get_option_chains` -> `get_option_quotes`) and the stock quote. Paper fill = the ASK, not the alert's Entry.
3. Fix the exit rule BEFORE seeing the outcome and record it in the log. Suggested start: sell at +100% or at 3:30 pm ET on expiry day, whichever comes first; stop-out at -50%.
4. Fill in `paper_fill_ask`, `paper_exit`, `paper_pnl_pct` and `result_pct` columns in `alerts_log.csv`.
5. Classify the setup (ATM 0DTE dip buy / momentum chase / OTM swing / macro) and keep a running hit rate per class.
6. Do not draw conclusions before about 30-50 alerts. Do not place real orders from the feed. No orders were placed in this analysis.

## Files
- `alerts_log.csv`: the 16 analysed alerts with outcomes and blank paper-trading columns.
- `HANDOVER.md`: this file.

## Update 2026-10-05: first live paper trade (MSFT 525c, expiry 10/5)
- Alert: MSFT 525c 0DTE, "Entry $2.60", Discord 6:34 AM PT (9:34 ET). Pacific time assumption now consistent with the options tape.
- Option minute bars from the open: first print 3.33 and a session low of 3.13 (13:32Z). **$2.60 never traded in regular hours today.**
  In the alert minute (13:34Z) the contract traded 3.78-4.73. This is the second case (after ORCL 135c on 9/29) where the alert's Entry is not obtainable.
  Any copy-trade backtest using alert prices will overstate returns. Use the quote at alert time instead.
- Paper fill: no historical bid/ask is available, so the fill is the high of the minute bar after the alert (13:35Z) = **5.18** (conservative; mid-ish estimate 4.43).
- Position state at 13:46Z: bid 5.95 / ask 6.30, mark 6.125 (+18% vs paper fill), IV 43%, delta 0.82, theta -3.10, break-even 531.13 vs spot 530.84, high so far 7.75.
- Setup class: momentum chase after a +2.1% opening gap (like MSFT 9/25 and META 800c, which lost, and ORCL, which won).
- Exit rule fixed in advance: sell at +100% (10.36), stop at -50% (2.59), or 3:30 pm ET (19:30Z, Robinhood's sellout time) whichever comes first.
  Settle by scanning the option's minute bars (instrument id 779c5a47-e697-49a3-a44b-4f0a63ead598) from 13:35Z for the first trigger, then fill `paper_exit` / `paper_pnl_pct` in `alerts_log.csv`.

## Update 2026-10-05 (2): MU 1050p 0DTE paper trade
- Alert: MU PUT 1050p expiry 10/5, "Entry $1.00", Discord 7:41 AM PT (10:41 ET). First put in the log (16 of 17 alerts are now calls),
  which weakens the earlier worry that the feed only shows bullish prints.
- Entry check: option minute bars traded 0.85-1.06 across 14:40-14:42Z, so $1.00 **was** obtainable. Unlike the MSFT and ORCL alerts, this entry price is credible.
  Stale entries are therefore not universal: 2 confirmed cases (ORCL, MSFT), 1 clean case (MU put). Keep checking each alert.
- Context: MU gapped down (open 1069.55 vs prev close 1074.89), hit 1055.56, bounced to ~1068.7, then rolled over to ~1063 as the put alert fired.
  The put jumped 0.63 -> 1.06 in about 3 minutes around the alert. Setup class: bearish rollover / momentum continuation scalp (new class, n=1).
- Paper fill 1.02 (high of the 14:42Z minute bar; no historical ask available). At 14:45Z: bid 1.11 / ask 1.14, mark 1.125 (+10%), IV 50%, delta -0.16, theta -7.35, break-even 1048.87 vs spot 1062.80 (needs about -1.3%).
- Same exit rule as the MSFT trade: +100% (2.04), -50% (0.51), or 3:30 pm ET (19:30Z). Settle from minute bars (instrument id 17095dba-cfa6-4766-a730-6358d6de3307).
  Caveat: a -50% stop on a ~$1 0DTE option sits inside ordinary noise (it moved 0.63 -> 1.06 in 3 minutes). The rule was fixed before the outcome, so keep it and note how often the stop is hit.

## Update 2026-10-05 (3): META 745c 0DTE paper trade
- Alert: META 745c expiry 10/5, "Entry $1.15", Discord 9:16 AM PT (12:16 ET), roughly 3h14m before Robinhood's 3:30 pm ET sellout.
- Entry check: the 16:16Z minute bar traded 1.01-1.17, so $1.15 was obtainable. Clean case (MU put also clean; ORCL and MSFT were stale). Tally: 2 stale, 2 clean of the 4 checked with option bars.
- Context: META +1.9% on the day, high 746.7 at 11:00 ET, then slid back below the 745 strike (742.1 at alert time). The call fell from 2.26 to 1.04 between 15:55Z and 16:15Z.
  Setup class: ATM 0DTE dip-buy / reclaim (same class as AMD, INTC x2, TSLA 347.5c, AAPL: 1 of 5 won before today).
- Paper fill **1.05** = the LIVE ask 1m42s after the alert (16:17:42Z; bid 1.01, size 33 on the ask). This is the first fill taken from a real quote, not a minute-bar-high proxy,
  so it is more reliable than the MSFT (5.18) and MU (1.02) fills. Mark 1.03, IV 35.5%, delta 0.30, theta -6.13, break-even 746.03 vs spot 742.13.
- Exit rule: +100% (2.10), -50% (0.525), or 3:30 pm ET (19:30Z). Settle from option minute bars from 16:18Z (instrument e1eac3d5-d919-4c79-89f0-ed60703ce785).

## Interim note 2026-10-05 9:27 AM PT: META 745c in profit (unrealized)
- Mark 2.06 (bid 2.02 / ask 2.10) vs paper fill 1.05 = about +96% (+92% at the bid). The +100% target (2.10) is 4 cents away; the settlement check will scan minute bars for the touch.
- META 744.66 is still BELOW the 745 strike: the gain is all time value from a ~$2.5 (0.34%) bounce off 742.1 (delta 0.30 -> 0.48, gamma 0.07, IV 35.5% -> 36.9%).
  Mechanism = long gamma on an ATM 0DTE: a small premium that reprices sharply on a small move. It is not intrinsic profit and can reverse (theta -7.5/day).
- Setup read: buy-the-dip call on a trending day (+1.9%, high 746.7), entered about $4 under the high, within 0.4% of the strike, 3 hours before sellout.
- One win does not validate the class. ATM 0DTE dip buys now stand at 6 trades with at most 2 winners (TSLA 347.5c, META 745c, pending settlement).
