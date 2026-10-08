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

## Settlement 2026-10-05 (scheduled check, 19:40Z)
All three paper trades settled mechanically from option minute bars using the rule fixed in advance (+100% / -50% / 3:30 pm ET).

| Trade | Setup class | Paper fill | Exit | Result | Alt: hold to 3:30pm ET |
|---|---|---|---|---|---|
| MSFT 525c 0DTE | momentum chase after +2.1% gap | 5.18 | 2.59 stop at 14:07Z (7:07am PT) | **-50%** | 3.80 (-27%) |
| MU 1050p 0DTE | bearish rollover | 1.02 | 0.51 stop at 14:50Z (7:50am PT) | **-50%** | 0.03 (-97%) |
| META 745c 0DTE | ATM dip buy | 1.05 | 2.10 target at 16:26Z (9:26am PT) | **+100%** | 0.46 (-56%) |

- Per contract: MSFT -$259, MU -$51, META +$105 = **-$205 on $725 of premium (-28%)**. Equal-dollar average return: 0%. The MSFT premium dominated because it was the largest.
- Nothing stopped out later reached its target (MSFT peaked at 7.75 before the fill window ended and never came back near 10.36; MU's best was 1.15 right after the alert). The stops did not cut winners.
- The +100% target on META mattered: holding that contract to 3:30 pm would have turned a double into -56%. The stop on MU mattered the other way (-50% instead of -97%). Exit discipline, not entry, decided these three outcomes.
- Fill caveat: MSFT and MU fills were minute-bar-high proxies (no historical ask). Stops and targets are assumed to execute at their level; on 0DTE contracts real slippage would likely make the stops slightly worse.

### Running hit rate by setup class (all alerts logged so far, entry-to-outcome as logged)
| Class | Wins / trades | Notes |
|---|---|---|
| ATM 0DTE dip buy | 2 / 6 | TSLA 347.5c (+285% at expiry), META 745c (+100% paper); AMD, INTC x2, AAPL lost |
| Momentum chase after opening spike | 1 / 4 | ORCL won (stale entry price); MSFT 9/25, META 800c, MSFT 10/5 lost |
| OTM swing (1-4 days) | 0 / 5 | GOOGL x3, GS, META 750c |
| Bearish rollover (put) | 0 / 1 | MU 1050p |
| Other | 0 / 1 settled (2 live) | MU 1150c lost; TLT 83c and TSLA 365c (spot 370.70 vs 365 on 10/2) still open and excluded from the ratio |

Combined view: of the 19 alerts so far, still no class shows a hit rate that clearly beats its payoff structure. Sample sizes are 1-6 per class, so none of this is evidence of an edge or its absence.

## Update 2026-10-06: two new paper trades (ORCL 144c, AMZN 257.5c)
Retroactive logging works: the option minute bars for a live contract can be pulled after the fact, so a missed alert can still be paper-filled from the bar after the alert time (bar-high proxy). Prefer live asks when the alert is fresh.

**ORCL 144c, expiry 10/9, "Entry $3.00" (Discord 10/5 10:51 AM PT, logged late)**
- Entry check: the alert-minute bars traded 2.98-3.03, so $3.00 was obtainable (clean). Paper fill 3.03.
- Context: ORCL gapped up to 146.65 at the open on 10/5, faded to a tight 143.2-144.1 range by midday, and the alert came inside that range (spot ~143.7, 0.2% below strike, 4 days to expiry). Closed 142.48.
- State at 7:41 AM PT 10/6: spot 144.51 (above strike), bid 3.00 / ask 3.10, mark 3.05 (+0.7% vs paper fill). IV 50%, delta 0.55, theta -0.43/day, break-even 147.05.
- Setup class: near-ATM multi-day call bought in a post-gap-up range (new class, n=1). Rule: +100% (6.06), -50% (1.515), or 3:30 pm ET on 10/9 (19:30Z).

**AMZN 257.5c, expiry 10/7, "Entry $0.70" (Discord 10/6 7:38 AM PT)**
- Entry check: 0.70 last printed at 14:35Z, about 3 minutes BEFORE the alert; by the alert minute the option traded 0.75-0.79 and 3 minutes later the ask was 0.89. Mildly lagged, not stale in the ORCL-135c/MSFT sense.
- Context: AMZN gapped up (253.40 open vs 251.40 close) and ground steadily higher to 254.88. Option had already gone 0.49 -> 0.77 since 14:30Z. Setup class: 1DTE OTM continuation call bought after the option had run (OTM swing class, previously 0 of 5).
- Paper fill 0.89 (live ask 14:41:25Z, ~3 min after alert; optimistic 0.77). Mark 0.88, IV 32%, delta 0.30, theta -0.68/day, break-even 258.38 (needs about +1.4%), Robinhood chance of profit 23%.
- Rule: +100% (1.78), -50% (0.445), or 3:30 pm ET on 10/7 (19:30Z).

**Entry-price audit so far (alerts checked against option minute bars):** clean 3 (MU put, META 745c, ORCL 144c); mildly lagged 1 (AMZN, ~3 min); stale/unobtainable 2 (ORCL 135c about 30 min; MSFT 525c never printed at 2.60).
Settlement is scheduled: AMZN at 10/7 19:40Z, ORCL 144c at 10/9 19:40Z.

## Update 2026-10-06 (2): AVGO 387.5c and AVGO 400c
Two alerts on the same name 11 minutes apart (Discord 10/6 8:19 and 8:30 AM PT). Both BUY calls, so this is a ladder of strikes/expiries (long both), not a vertical spread. Logged ~1h25m later from option minute bars; both entries are clean (alert prices sit inside the alert-minute bars).

**Context:** AVGO ran 349.86 (10/2 open) -> 377.96, about +8% in 3 sessions, +4.3% today (gap to 366.8, surge to ~377 by 10:10 ET, then a tight 374.5-379.2 range). Both alerts landed in that consolidation, within about 0.3% of the day's high of 379.2.

| | AVGO 387.5c exp 10/9 | AVGO 400c exp 10/12 |
|---|---|---|
| Alert / entry | 8:19 AM PT / 2.50 | 8:30 AM PT / 1.15 |
| Spot at alert, OTM | ~378, 2.5% OTM, 3 days | ~377.6, 5.9% OTM, 4 days |
| Paper fill (bar-high proxy) | 2.78 (optimistic 2.61) | 1.17 (optimistic 1.13) |
| State at 9:44 AM PT | bid 2.27 / ask 2.35, mark 2.31, **-17% vs fill** | bid 1.13 / ask 1.18, mark 1.155, **-1% vs fill** |
| Greeks | delta 0.27, theta -0.77/day, IV 41%, BE 389.81 | delta 0.13, theta -0.32/day, IV 37%, BE 401.16 |
| Robinhood chance of profit | 21% | 11% |
| Rule | +100% 5.56 / -50% 1.39 / 3:30pm ET 10/9 | +100% 2.34 / -0.585 / 3:30pm ET 10/12 |

- Setup class: multi-day OTM call on a stock that had already run (OTM swing class, previously 0 of 5; AMZN 257.5c also pending). Not an opening-spike chase, since both were bought after the consolidation formed.
- AVGO is flat since the alert (377.96 now vs ~378), yet the 387.5c is -17% vs the fill: that is time decay and a small IV drift, i.e. a "stock goes nowhere" scenario already costs these trades.
- Paper-fill sensitivity: the option rose 15% in the three minutes after the 8:19 alert (2.42 -> 2.78), so the proxy fill is 11% above the alert price. Copying at the alert price would have been unachievable.
- Settlement: 387.5c on 10/9 19:40Z (with the ORCL 144c check), 400c on 10/12 19:40Z. Note 10/12 is Columbus Day (equity options trade); weekend theta will hit the 400c before then.

## Settlement 2026-10-07: AMZN 257.5c (alert 10/6 7:38 AM PT)
- Paper fill 0.89, rule +100% (1.78) / -50% (0.445) / 3:30pm ET 10/7. Result: **-57%**. The option held 0.69-1.25 all of 10/6, then **opened 10/7 at 0.38**, gapping through the stop (prior-day close ~1.03). The stop fills at the open, 0.38, not at 0.445.
- It then reversed: the option rose to a high of 2.36, first touched the +100% level (1.78) around 16:30Z, and was 1.88 at 3:30pm ET (+111% vs the fill). AMZN gapped down at the open, then rallied back above the 257.5 strike intraday (inferred from the option path; I did not pull the 10/7 stock bars). The rule exit and the hold-to-3:30 outcome are opposite signs.
- Class: OTM swing (1-4 days) is now 0 of 6 under the fixed rule, though hold-to-expiry would have scored this one a win.

### Exit-rule comparison on the four settled paper trades (same rule, hindsight view)
| Trade | Rule result (+100/-50/3:30) | Hold to 3:30pm ET |
|---|---|---|
| MSFT 525c 0DTE | -50% (stop) | -27% |
| MU 1050p 0DTE | -50% (stop) | -97% |
| META 745c 0DTE | +100% (target) | -56% |
| AMZN 257.5c 1DTE | -57% (stop, gap) | +111% |
| **Average** | **-14%** | **-17%** |
The rule helped on MU and META and hurt on MSFT and AMZN, ending roughly level with simply holding. Four trades cannot rank the rules. The overnight-gap case (AMZN) is a reminder that stops on multi-day contracts do not protect at the stop level.
Still open: ORCL 144c and AVGO 387.5c (settle 10/9), AVGO 400c (10/12), TSLA 365c and TLT 83c (expiry values to be reported 10/9).

## Update 2026-10-08: INTC 117c, expiry 10/9 (alert 7:35 AM PT)
- Entry check: "Entry $0.16" sits inside the 14:35Z minute bar (0.16-0.17). Clean. Paper fill 0.17 (bar-high proxy).
- Context: INTC gapped down 2.5% (113.12 -> 110.34), hit 108.55, bounced to 111.6 around 7:25 AM PT, then faded. The alert arrived during the fade; the call had run 0.13 -> 0.23 on the bounce and was back to 0.16. The option closed 10/7 at 0.77, so this is buying a contract that had already lost about 80% of its prior-day value.
- Setup: deep-OTM (5.9%) 1DTE lottery, IV about 70%, delta 0.05. Class: OTM swing/lottery, now 0 of 7.
- **Settled by rule within 18 minutes:** the -50% stop (0.085) was first touched at 14:53Z (7:53 AM PT; bar low 0.08). Paper result **-50%**. At 8:02 AM PT the mark was 0.075 (bid 0.07 / ask 0.08), spot 109.2, break-even 117.08 vs spot 109.2 (needs +7.2%), Robinhood chance of profit 4%. Hold-to-3:30pm-10/9 value to be added by the 10/9 check for the exit-rule comparison.
- **INTC pattern:** this is the third INTC dip-buy call alert in the log (116c 9/28 -96%, 120c 9/30 -67%, 117c 10/8 -50%), all losers. INTC peaked 127.4 on 9/24 and is now about 109 (-14%).
- Entry-price audit: clean 6 (MU put, META 745c, ORCL 144c, AVGO 387.5c, AVGO 400c, INTC 117c), mildly lagged 1 (AMZN), stale 2 (ORCL 135c, MSFT).

## Update 2026-10-08 (2): MU 1100c, expiry 10/9 (alert 11:31 AM PT = 2:31 PM ET)
- Entry check: the alert-minute bar (18:31Z) traded 1.01-1.07; $1.00 is one cent below it (the 18:25Z bar closed 1.01). Essentially clean. Paper fill 1.13 (bar-high proxy; optimistic 1.05).
- Context: MU spiked +7% on 10/7 (open 1017, close 1088) and gave back -4.5% today (low 1032.4 at 10:20 AM PT). A 15-minute bounce (MU 1038 -> 1049) lifted this call 0.77 -> 1.13, and the alert landed at that local top; the call fell to 0.85 two minutes later. It closed 10/7 at **11.00** and was 0.81 at 11:46 AM PT.
- Setup: 5.0% OTM 1DTE call, IV 65%, delta 0.05, theta -1.88, break-even 1100.81 vs spot 1039.55 (needs +5.9%), Robinhood chance of profit 4.8%. Class: OTM swing/lottery, now 0 of 8.
- State at 11:46 AM PT: bid 0.80 / ask 0.82, mark 0.81 = **-28% vs the paper fill** (-19% vs the alert price). Stop 0.565 and target 2.26 not touched yet (lowest low since the fill 0.74).
- **MU pattern:** third MU alert in the log, with alternating direction: 1150c call (10/1, -100%), 1050p put (10/5, -50% by rule), now 1100c call. MU has swung 1017 -> 1088 -> 1040 in two days, so every alert has been well timed for a reversal after it was posted.
- Settlement: added to the 10/9 19:40Z check.
