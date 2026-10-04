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
