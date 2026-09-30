# Strategy Backtester + Swing Scanner (BTC/ETH spot, SPY/SPX options, live stock screening)

Research-first automation across three things: **backtests of trading strategies
against historical data, and a live technical screener that suggests candidates
with entry/stop/target. Nothing here places a live order.** That's a deliberate
scope decision, not a placeholder — automating real-money trades before a strategy
has been validated is how accounts get blown up, and a screener's output is a
research starting point, not a signal to act on unexamined.

## Scope and what's deliberately NOT here

- **No live execution.** There is no code here that calls a broker/exchange to place
  an order. If/when a strategy earns that step, it's a separate, explicit addition —
  not something this repo does implicitly.
- **BTC/ETH spot, SPY/SPX options, and a live stock scanner.** Forex and commodities
  are still out of scope: no broker/data connector for either is available in this
  environment.
- **Long-only, no leverage on the crypto side; long calls/puts only on the options
  side.** No shorting the underlying, no spreads, no margin.
- **The scanner is unvalidated by design.** Its entry/stop/target come from
  well-understood indicators (RSI, ADX, ATR), but the *combination* has no
  backtested track record in this repo, unlike every strategy above it.

## Why a backtest first

Three well-known retail strategy families are implemented as a comparison set,
each with documented failure modes (see the docstring in each file under
`trading_bot/strategies/`):

- `buy_and_hold` — the benchmark every active strategy must beat after costs.
- `sma_crossover` — trend-following; whipsaws in choppy markets, lags reversals.
- `rsi_reversion` — mean-reversion; bets against the trend, dangerous in a real
  downtrend, and its backtest results are very sensitive to the window chosen.
- `donchian_breakout` — momentum; eats many small losses on false breakouts while
  waiting for the rare big trend that makes it profitable.

None of these is presented as "the" strategy — the CLI runs all four so the data,
not a guess, decides which (if any) is worth pursuing further, and over what
period. Expect all of them to sometimes lose to buy-and-hold; that is itself a
useful result, not a bug.

## Data source

Historical OHLCV comes from **Coinbase Exchange's public REST API**
(`api.exchange.coinbase.com`, no key required) via `trading_bot/data/fetch.py`,
covering BTC-USD/ETH-USD daily bars from 2020-01-01 onward with no gaps.

Two other sources were tried and rejected, for reasons worth knowing if this ever
needs a third:

- **`api.binance.com`** returns HTTP 451 ("restricted location") from this
  environment's egress IP, regardless of network policy — a Binance-side
  geo-block, not something an allowlist change can fix.
- **`api.binance.us`** answers, but its BTCUSD/ETHUSD history has a **~586-day
  gap** (roughly mid-2023 to early-2025), coinciding with Binance.US losing its
  USD banking rails in 2023. A naive `pct_change()` across that gap produced a
  fabricated +285% "one-day return" that silently wrecked the volatility/Sharpe
  numbers on a first run of this backtest — caught by inspecting an
  implausibly high annualized volatility figure, not by anything that errored.

Because of that, `fetch_klines()` now refuses to return data with any gap larger
than one bar (raises `RuntimeError` instead of letting the caller compute a
return across it) — a live guard against the same class of bug recurring with a
different data source later.

If `api.exchange.coinbase.com` isn't reachable in a given environment, its
network access setting is at: title bar → environment selector → **Edit** →
**Network access**.

## Results so far (2020-01-01 through now, daily bars, 5 bps fee + 10 bps slippage)

|          | BTC total return | BTC CAGR | BTC Sharpe | ETH total return | ETH CAGR | ETH Sharpe |
|---|---|---|---|---|---|---|
| buy_and_hold          | 10.72x | 44.1% | 0.91 | 19.58x | 56.7% | 0.96 |
| sma_crossover_20_50   |  6.31x | 34.4% | 0.91 | 13.44x | 48.6% | 0.96 |
| rsi_reversion_14_30_60|  0.89x | 9.9%  | 0.45 |  0.39x |  5.0% | 0.32 |
| donchian_breakout_20  |  8.24x | 39.1% | 0.97 | 18.76x | 55.7% | 1.06 |

Buy-and-hold wins on both assets. Nothing here beats it after costs over this window.
RSI mean-reversion is the standout failure — exactly the predicted mechanism: it kept
buying dips during real downtrends with no floor under them. Donchian breakout came
closest (and edges buy-and-hold on ETH's Sharpe ratio, i.e. a smoother ride for
slightly less return), which fits its designed tradeoff: give up some upside for a
few large trend-catching wins funded by many small breakout failures. None of this
should be read as "so buy-and-hold is correct" either — five years dominated by a
strong secular crypto uptrend is a soft test for a trend-following benchmark.

**That prediction was checked, and it inverted exactly as expected.** Re-running the
same four strategies over the 2021-11-01 to 2022-11-30 bear market (`--start
2021-11-01 --end 2022-11-30`):

|          | BTC total return | BTC Sharpe | BTC max DD | ETH total return | ETH Sharpe | ETH max DD |
|---|---|---|---|---|---|---|
| buy_and_hold          | -71.9% | -1.45 | -76.7% | -70.1% | -0.83 | -79.4% |
| sma_crossover_20_50   | -46.7% | -1.57 | -53.8% | -39.1% | -0.78 | -45.3% |
| rsi_reversion_14_30_60|  +0.6% |  0.22 | -40.4% | -15.8% |  0.01 | -57.6% |
| donchian_breakout_20  | -34.2% | -0.86 | -39.2% | -45.5% | -0.91 | -57.3% |

Buy-and-hold is now the **worst** performer on both assets, by a wide margin. Every
active strategy preserved capital better simply by having an exit rule and going
flat during the crash — RSI mean-reversion, the strategy that lost the worst in the
bull window, comes out roughly flat on BTC here and loses the least on ETH.

**Conclusion: there is no single best strategy — only a best strategy per regime**,
and this repo has no regime detector. Picking one strategy and running it live would
mean betting the current regime looks like whichever window was used to justify the
choice. The next honest step is walk-forward validation, not adopting either table
above at face value.

### Walk-forward validation

A single fixed-parameter backtest, however many windows you try, still involves a
human eyeballing results and picking a winner after the fact — that's look-ahead
bias by another name. Walk-forward removes the human from parameter selection: for
each strategy family, `trading_bot/backtest/walk_forward.py` re-picks the
best-scoring parameters using only the trailing `--train-days` (default 365), locks
them in, tests that fixed choice on the next `--test-days` (default 90) it has never
seen, then rolls forward and repeats — chaining every out-of-sample segment into one
continuous equity curve. This is close to what actually running one of these
strategies live and periodically re-tuning it would look like.

```
python -m trading_bot.walk_forward_cli --symbols BTCUSD ETHUSD --start 2020-01-01
```

Results (same cost assumptions, buy-and-hold benchmarked over the identical
out-of-sample span so it's apples-to-apples):

|          | BTC total return | BTC Sharpe | ETH total return | ETH Sharpe |
|---|---|---|---|---|
| buy_and_hold (same span) | +189% | 0.61 | +265% | 0.68 |
| sma_crossover (walk-forward) | +40% | 0.35 | **+712%** | **0.91** |
| rsi_reversion (walk-forward)  | -52% | -0.16 | -29% | 0.06 |
| donchian_breakout (walk-forward) | +97% | 0.49 | +333% | 0.72 |

This is a genuinely different picture from either single-window result, and more
trustworthy than both: **on BTC, buy-and-hold still wins outright** even when the
other strategies get to re-tune every quarter. **On ETH, re-optimized SMA crossover
clearly beats buy-and-hold**, on both return and Sharpe — the one result in this repo
that looks like real, non-overfit edge rather than an artifact of window choice.
RSI mean-reversion loses out-of-sample on both assets, consistent with every other
test run in this README — three different evaluation methods now agree it's the one
family to rule out.

Two caveats before acting on the ETH/SMA result: (1) `trading_bot/*_segments.csv`
(written next to the other outputs) shows the winning fast/slow window drifting
across quarters rather than converging on one stable setting — consistent with a
real but modest edge, not a sharp signal, and (2) this is still one full walk-forward
run, not a distribution — rerunning with a different `--train-days`/`--test-days`
split before trusting the ETH result would be the next thing to check, the same way
the bear-market run checked the first backtest.

### Dip-buy with a fixed take-profit target

A different kind of strategy from the four above: instead of holding "as long as an
indicator says to," `trading_bot/strategies/dip_buy_bracket.py` +
`trading_bot/backtest/bracket_engine.py` implement "buy after a pullback, sell at a
fixed profit target" — entry triggers when price is at least `--pullback-pct` below
its trailing `--lookback-days` high, exit is whichever of a take-profit, a stop-loss,
or a max holding period is hit first (checked against each day's high/low, not just
the close, since a price target is a real limit/stop order). A take-profit with no
stop-loss has unbounded downside on any trade that doesn't recover, so a 10%
stop-loss and a 90-day max hold are on by default even though neither was specified —
both configurable, `--stop-loss-pct -1` disables the stop.

```
python -m trading_bot.bracket_cli --symbols BTCUSD ETHUSD --take-profit-pct 0.15 --pullback-pct 0.10 --stop-loss-pct 0.10 --max-holding-days 90
```

Result, 2020-2025, 15% target / 10% pullback trigger / 10% stop / 90-day max hold:

|          | total return | Sharpe | max drawdown | trades | win rate | avg hold |
|---|---|---|---|---|---|---|
| BTC dip_buy | +24% | 0.29 | -74.8% | 84 | 45.2% | 15.8 days |
| BTC buy_and_hold | +1,068% | 0.91 | -76.7% | 1 | — | — |
| ETH dip_buy | **-40%** | 0.15 | **-91.1%** | 145 | 42.8% | 8.9 days |
| ETH buy_and_hold | +1,966% | 0.97 | -79.4% | 1 | — | — |

Loses badly on both, catastrophically on ETH — an actual loss of principal over a
period buy-and-hold turned into a 20x. This confirms the concern raised before
building it: the entry rule ("price dropped 10%, buy it") is the same bet as
`rsi_reversion`, which lost in every evaluation already run in this README (bull
backtest, bear backtest, walk-forward). A fixed take-profit on the exit side doesn't
change that — it only decides how the *winning* trades get closed, not whether the
entries are catching real bottoms.

The more useful thing this run shows is *why* it loses, because it's not obvious from
the win rate alone: at a 45%/43% win rate with a 15%-gain-vs-10%-loss payoff, the
average trade has slightly *positive* expectancy on paper (≈+1.3% BTC, ≈+0.7% ETH,
before costs) — the kind of number that looks fine in isolation. It still loses money
because dip-buy entries aren't independent: in a sustained decline, each stop-out is
immediately followed by a fresh entry (price is *still* freshly down 10% from its now
also-falling recent high), so real drawdowns produce clusters of correlated,
back-to-back losing trades rather than the independent coin-flips the expectancy math
implicitly assumes. That correlation is what a raw win-rate/payoff calculation misses
and what actually sank the equity curve — the 2022 bear market and 2025 chop are
exactly where the trade count and losses concentrate on the chart.

## SPY/SPX options: 4h trend filter + 5m pullback entry, 10% premium target

A different request entirely: trade SPY/SPX options (not the underlying), using the
4h chart to confirm trend direction and the 5m chart to time entries on a pullback,
targeting **10% profit on the option's premium** (not the underlying's price move).

### Real historical option data turned out to be unusable here — for a specific,
### verifiable reason, not "options are hard"

`get_option_historicals` genuinely supports 5-minute and 4-hour bars for expired
contracts (confirmed: a SPY $500 call expiring June 2025, fetched from March 2025,
showed real, richly varying prices tracking the actual April 2025 tariff-crash
volatility). The problem is that the *underlying* equity data
(`get_equity_historicals`) and the *option* premium data don't have a genuine period
in common in this environment:

- **Underlying (SPY 4h/5m)**: confirmed fake — flat, often zero-volume, sometimes
  flagged `interpolated: true` and sometimes not — for every date checked from
  January 2025 through October 31, 2025. Real (correct volume, real price movement)
  from **2025-11-03 onward**, with a clean, sharp cutover on that exact date.
- **Option premiums**: confirmed real for a contract expiring June 2025. Confirmed
  **flat/frozen for its entire lifespan** (a single repeated price for hundreds of
  bars) for five separate contracts checked with expirations in Dec 2025, Jan 2026,
  and three in the May-Sept 2026 range — every expiration at or after the point
  where the underlying data becomes real.

So: real signals need data from Nov 2025 on; real option prices are only confirmed
before that. There is no known window satisfying both. (This was checked thoroughly
— 7 separate probes from both directions — before concluding it's a real gap, not a
bad date choice.)

### The workaround: real signals, modeled option prices

`trading_bot/options/synthetic_bracket.py` uses the real, gap-free SPY underlying
price history (2025-11-03 onward) to generate entry signals and walk the actual
price path, but prices each option leg with **Black-Scholes** instead of a measured
premium. Every assumption this introduces is significant enough to repeat here,
not just in the module docstring:

- **Volatility is a proxy, not a measurement.** It's the trailing 20-trading-day
  *realized* volatility of the underlying as of each trade's entry — a common rough
  stand-in for *implied* vol, but they are genuinely different numbers, especially
  around anticipated events.
- **"Sticky vol"**: that volatility is held fixed for the life of each trade. Real
  option prices are driven substantially by implied vol itself expanding and
  crushing, independent of the underlying's move — none of that is modeled.
- **European exercise** (exact for SPX, an approximation for SPY's American-style
  contracts — small effect for a short-dated, not-deep-ITM option).
- **No real bid-ask spread** (there's nothing to measure); a flat `--cost-rate`
  assumption stands in for it, same caveat as every other cost assumption in this
  README.

Entries: the same 4h-bias + 5m-pullback-reclaim logic already built for crypto
(`trading_bot/strategies/mtf_pullback.py`), run on real SPY data, tightened to a
0.3%-pullback / 1-trading-day-cooldown trigger to keep the number of real contracts
needed to a workable ~22 over a 4-month window (the initial untightened rule fired
371 times in the same span). Contract resolution used real Robinhood option chains
(ATM strike, ~7-14 days to expiration) — only the *premium path*, not the contract
identity or the underlying price, is synthetic.

### Result: real signal, wildly cost/stop-sensitive

```
python -m trading_bot.synthetic_options_cli \
    --underlying-4h data_cache_options/SPY_4h.csv --underlying-5m data_cache_options/SPY_5m.csv \
    --entries data_cache_options/SPY_call_entries.csv --targets data_cache_options/SPY_call_targets.csv
```

22 real entry signals, 10% take-profit fixed, swept across stop-loss width and a
one-way cost assumption (charged on both legs):

| cost (one-way) | stop | trades | win rate | total return |
|---|---|---|---|---|
| 0.0% | 15% | 22 | 59.1% | -20.0% |
| 0.0% | 20% | 22 | 68.2% | -12.4% |
| 0.0% | 30% | 22 | 81.8% | **+33.5%** |
| 0.0% | 50% | 21 | 81.0% | -68.4% |
| 0.5%/leg | 30% | 22 | 81.8% | +6.9% |
| 1.0%/leg | 30% | 22 | 81.8% | -14.6% |
| 3.0%/leg | 50% (original ask) | 21 | 81.0% | **-92.7%** |

Full grid in `reports_out_synth_options/sensitivity_grid.csv`. The headline: **the
entry signal alone (zero cost) is right at the breakeven edge with a tight 15% stop**
(59.1% win rate against a 10%-gain/15%-loss payoff needs 60% to break even) **and
shows real edge with a wider 30% stop** (81.8% win rate, +33.5%) — but that edge
evaporates under any realistic cost assumption above ~0.5% per leg, and the specific
combination originally asked about (50% stop, no explicit cost given, modeled here
at a conservative 3%/leg) loses 93% of capital. The 50%/10% stop/target combination
is a structurally bad risk/reward (a 14:1 loss-to-win ratio needing a ~93% win rate
just to break even) *independent of whether the entries are any good* — this is the
same lesson as `dip_buy_bracket`'s asymmetric-payoff failure, in a different guise.

**Read this as**: the 4h+5m pullback timing may have real value, but nothing here
should be treated as validating a 50%-stop/10%-target SPY options strategy — that
specific shape loses regardless of entry quality, and even the promising 30%-stop
result is one 4-month, 22-trade, model-priced sample. It has not been walk-forward
validated the way the crypto strategies were, and SPX was never tested (no reason to
expect a different data-availability outcome, but not verified).

## Paper trading: ETH walk-forward SMA crossover, no orders placed

The first thing built after the user asked for real order placement, per the
sequence we agreed on instead: validate → paper-trade → only then consider
execution, with every order requiring human approval. This module places **no
orders**; it logs what the strategy would have done against real, current data.

It exists because of the parameter-drift finding above: locking in whichever
setting looked best on historical data (fast=20, slow=30, chosen in hindsight)
would be exactly the look-ahead bias walk-forward validation exists to prevent.
`trading_bot/paper_trading/engine.py` instead re-runs the *actual* validated
process live — re-selecting parameters from a trailing 365-day window every 90
days using `backtest/walk_forward.py`'s own selection logic (imported, not
reimplemented), then tracking day-by-day what position that produces. State
persists to JSON so a daily run picks up where the last one left off, and
calling it twice on the same day is a no-op (checked directly in
`tests/test_paper_trading.py`).

```
python -m trading_bot.paper_trading_cli --symbol ETHUSD --state-file paper_trading_state/ETHUSD_sma_crossover.json
```

Bootstrapped against real data on 2026-09-25: the live trailing-365-day
optimization currently selects **fast=10, slow=100** (notably *not* the
(20,30) that dominated the historical segment log — a reminder that "the mode
so far" is not a fixed fact, it can and does change), and that parameter set is
currently **long** ETH, entered notionally at $2,693.31. Paper equity starts at
$10,000 and updates by one real day each time the CLI is re-run against fresh
data — there is no forward-tested track record yet, because none exists until
time actually passes.

## Swing-trading stock scanner: live candidates with entry/stop/target

A different kind of tool from everything above: not a backtest, a **live screener**.
Robinhood's scanner API (`create_scan`/`run_scan`) can screen the entire market
against real technical filters (RSI, ADX, moving averages, ATR, volume, market cap,
...) in one call — no need to fetch bulk historical data for hundreds of tickers.

The saved scan (`Swing pullback-in-uptrend scan`) looks for: real stocks (not
ETFs/crypto), price > $10 and market cap > $300M (avoid penny/micro-cap noise),
30-day average volume > 500k shares (liquidity), a positive trailing-month return
with ADX(14) > 20 (a confirmed uptrend, not just noise), and RSI(14) between 35-50
(cooled off from a pullback, but not in a full oversold reversal). It's the same
trend-plus-pullback family as `mtf_pullback.py`, applied as a screen instead of a
single-symbol signal.

```
python -m trading_bot.scanner_cli --scan-json data_cache_scanner/swing_scan_20260924.json
```

**Entry uses the daily `Close` the signal was actually computed from, not the live
`Last` price** — every scan filter runs on completed daily bars, so using the live
quote as "entry" would silently blend yesterday's signal with today's unrelated
price move. A live run (2026-09-24) found 38 candidates; **19 of the 38 (half!)
had already moved more than 1.5% between that signal close and the live quote by
scan time** — e.g. Trane Technologies (TT) closed at $438.54 but was already
trading at $454.44, a 3.6% move the signal never priced in. Those are flagged
`stale` in the output, not silently included as if still actionable.

Entry/stop/target come from **ATR (Average True Range)**, not the scanner's own
Support/Resistance columns — those returned at least one real case (TT again)
where "Resistance" sat *below* the live price, which would make a nonsensical
profit target already behind you. Defaults: stop = entry − 1.5×ATR, target =
entry + 3×ATR (a 2:1 reward:risk), both adjustable via `--atr-stop-mult`/
`--atr-target-mult`.

**This is a screening tool, not a validated strategy.** Unlike every crypto/SPY
result above, "RSI 35-50 pullback in an ADX-confirmed uptrend" has not been
backtested in this repo — there's no historical win rate, no walk-forward result,
nothing. It's a live filter built from indicators that are individually
well-understood, not a strategy with a track record. Treat its output as a
starting shortlist to research further, not a signal to act on directly — and
skip anything flagged stale outright, since its entry price no longer reflects
where the stock actually trades.

## Paper trading: swing-scanner stocks, no orders placed

The scanner above has zero backtest, so before it goes anywhere near real orders
it needs the same treatment the ETH strategy got: paper trade it, with a
graduation bar agreed in advance so results can't be read as "good enough" after
the fact just because time pressure exists. That bar, fixed before any paper
results existed: **≥20-30 completed round-trip trades, ≥2-3 months elapsed,
positive expectancy after a 5-10bps cost assumption, and a win rate meaningfully
above the ~33% breakeven the 2:1 reward:risk (3×ATR target / 1.5×ATR stop)
implies.** Even clearing all of that, execution safety (sizing, loss caps, a kill
switch, per-order approval) still wouldn't exist yet.

Structurally different from the ETH paper trader: the scanner surfaces *several*
stock candidates at once, not one continuous position, so
`trading_bot/stock_paper_trading/engine.py` tracks a small portfolio — up to
`max_concurrent` (default 8) positions simultaneously, each sized at a **fixed
10% of the portfolio's original capital** (not of current equity, so position
size doesn't grow or shrink with performance), each with its own ATR-based
stop/target and a 20-trading-day max hold (a real swing-trading horizon, shorter
than the crypto bracket engine's 90-day default). Refreshing the scan is a live
`run_scan` call only an agent session can make — same constraint as the SPY
options data-fetching work — so, like `synthetic_options_cli.py`, there's no
self-contained CLI here; `trading_bot/scanner/entry_exit.py`'s
`select_new_candidates` picks fresh, non-stale, not-already-held symbols from
whatever a live scan pull returns, and a daily Routine drives the loop end to end.

Bootstrapped 2026-09-25 with a fresh scan pull: 8 positions opened (all 8
concurrent slots filled from that day's non-stale candidates) — STNG, BKSY, OHI,
TX, TARS, NVMI, VOD, HPQ — $1,000 each, $2,000 cash held in reserve, $10,000
total paper capital. A second daily Routine (separate from the ETH one) advances
this portfolio: closes any position that hit its stop/target/20-day timeout using
that day's real OHLC, opens new positions from a fresh scan pull into freed
slots, and — like the ETH routine — stays quiet on routine days, only surfacing a
message for a trade closing, something anomalous, or the graduation bar being met
for the first time.

## Smart Money Concepts (SMC): SPY/SPX/IWM, 4h structure, 1-2 week swing target

A "BOS continuation + CHoCH exit" backtest, from definitions given verbatim:
higher-highs/higher-lows = bullish structure (vice versa for bearish); a swing
high/low is the point that caused the opposing swing low/high; a "strong" swing
point is the one that preceded a break of structure in its direction; a Break
of Structure (BOS) signals trend continuation and an expected pullback; a
Change of Character (CHoCH) is the first break *against* the prevailing trend,
signaling a possible reversal.

**Swing detection and its inherent lag** (`trading_bot/strategies/smc_structure.py`):
swing points are found with a symmetric fractal — bar *i* is a swing high/low
only if it's strictly the max/min of the `swing_length` bars on both sides of
it. This means a swing point can't be confirmed until `swing_length` bars after
it forms (there's no way to know "nothing since then exceeded it" any sooner).
Every downstream signal (trend, BOS, CHoCH, strong high/low, HH/HL/LH/LL
labels) is applied starting only from that confirmation bar, never from the
bar the swing actually occurred on — this is the crypto/options work's
no-lookahead discipline applied to a new kind of signal. BOS/CHoCH are
close-based breaks of the most recently *confirmed* swing level, not
wick-based, mirrored consistently for both directions.

**The trade rule** (`trading_bot/strategies/smc_bos_choch.py`, long-only by
design — the rule is named "CHoCH exit," not "CHoCH flip"): after a bullish
BOS, wait for the next confirmed swing low to print *higher* than the previous
one (a genuine HL — the pullback ending and the strong low forming); enter
long there. Exit to flat the moment a bearish CHoCH breaks that same reference
low. Going long again after an exit requires an entirely fresh bullish
break-and-pullback cycle.

**Data:** 4h bars, Nov 3 2025 through Sep 25 2026 (~11 months, ~2-3 real bars/
trading day), the same window for all three symbols so the comparison is
apples-to-apples. SPY and IWM (`get_equity_historicals`) hit a hard real-data
floor at 2025-11-03 — everything earlier came back flat/zero-volume in this
environment, the same boundary found during the SPY-options work. SPX
(`get_index_historicals`) has real data much further back (confirmed real for
October 2024, empty for September 2024 and earlier in spot checks) but only
answers narrow (~1-month) date ranges per call, and mixes real bars with
explicit `interpolated: true` gap-fill bars that were dropped before use; SPX's
longer history wasn't pulled for this run to keep the three-way comparison on
identical dates, but it's available for a bigger-sample SPX-only follow-up.

**Exit early beats waiting out a slow CHoCH.** The first version exited only
on CHoCH, which let some trades run 6-13 weeks (max 92 days, IWM) waiting for
a real reversal signal — well past the requested 1-2 week horizon. Per
explicit direction, `SmcBosChochStrategy` now takes a `max_holding_bars`
parameter (default 20) that forces an exit on whichever comes first: a
bearish CHoCH, or the cap. Bar count, not calendar days, because bar density
varies by symbol and even by day: SPY/IWM average ~1.4 real bars/trading day
(many days have only one usable 4h bucket, not two), SPX averages ~2.1 —
so a 20-bar cap lands around 2-3 calendar weeks on average, not an exact
2-week deadline.

**Results (5bps fee + 10bps slippage, `swing_length=3`, `max_holding_bars=20`):**

| Symbol | Trades | Win rate | Total return | Sharpe | Max DD | Avg win | Avg loss | Max hold (days) |
|---|---|---|---|---|---|---|---|---|
| SPY | 7  | 14% | -4.4% | -1.10 | -7.3% | +5.2% | -1.6% | 29 |
| IWM | 6  | 33% | -2.1% | -0.28 | -9.0% | +3.0% | -2.0% | 30 |
| SPX | 15 | 33% | -3.3% | -0.55 | -6.4% | +1.9% | -1.3% | 11 |

Honest read: still **not a profitable strategy on this data**, and the sample
(6-15 trades over 11 months) remains too small to conclude much either way.
Capping the hold does what it was supposed to — the worst-case tail drops from
92 days to 30, and win rates rise (33% for IWM/SPX vs 14-20% uncapped) since
more trades now close on a timeout rather than grinding out a loss waiting for
CHoCH. But it comes at a real cost: SPX's uncapped run was carried almost
entirely by one +11.3% trade that ran 56 days — the cap would have closed that
same trade far earlier, and SPX's total return dropped from roughly breakeven
(-0.9% uncapped) to -3.3% capped. That's the actual tradeoff of exiting early
on a trend-continuation rule: it caps the downside tail and the upside tail
together, since both come from the same "let it run" mechanism. A
`swing_length` sweep (2/3/5) didn't change the overall picture — it mostly
traded off number-of-trades against per-trade size, not the underlying
win/loss shape.

## Does the ETH walk-forward SMA edge generalize to SPX/Russell 2000?

The one result in this repo that looked like real edge — walk-forward
re-optimized SMA crossover beating buy-and-hold on ETH (+712% vs +265%,
Sharpe 0.91 vs 0.68) — was tested on equities to see if it's a genuine SMA
effect or an ETH-specific artifact. Same methodology exactly: `run_walk_forward`
re-picks `fast`/`slow` from the trailing 365 days, locks them in, tests on the
next unseen 90 days, rolls forward; daily bars, 5bps fee + 10bps slippage,
`periods_per_year=252`. Data: SPX and IWM (Russell 2000 ETF) daily closes,
2015-01-02 through 2026-09-25 (`data_cache_smc/SPX_daily.csv`,
`IWM_daily.csv`) — unlike the 4h SMC data, daily bars for both go back over
a decade with no gaps, since the Nov-2025 real-data floor found earlier in
this repo turned out to be specific to *intraday* historicals, not daily ones.

**Result: it does not generalize — buy-and-hold wins clearly on both,** the
opposite of the ETH case:

| | Total return | CAGR | Sharpe | Max DD | Trades |
|---|---|---|---|---|---|
| SPX buy-and-hold | +284% | 13.4% | 0.79 | -33.9% | 1 |
| SPX walk-forward SMA | +62% | 4.6% | 0.48 | -24.1% | 37 |
| IWM buy-and-hold | +156% | 9.2% | 0.50 | -42.3% | 1 |
| IWM walk-forward SMA | **-7.9%** | -0.8% | 0.02 | -40.6% | 41 |

On IWM the re-optimized strategy loses money outright over a span where
simply holding would have returned +156% — not just "underperforms," net
negative after costs. On SPX it's positive but roughly a fifth of
buy-and-hold's return for lower Sharpe and only a smaller drawdown reduction
(-24% vs -34%) to show for it. Same parameter-drift pattern as the ETH run
(`data_cache_smc/{SPX,IWM}_sma_walkforward_segments.csv` — winning
fast/slow window changes almost every quarter, never converges), but here it
isn't compensated by an edge large enough to matter.

**Read plainly: SMA crossover's ETH edge was asset-specific (or crypto-regime
specific), not a general "re-optimized trend-following beats buy-and-hold"
effect.** Applied to the two large-cap/small-cap US equity indices requested
here, the exact same walk-forward process that found edge on ETH finds none
on SPX and a real loss on IWM. This doesn't retroactively invalidate the ETH
result (which still has its own caveats above), but it rules out treating
"walk-forward SMA" as a strategy that travels across assets — each
market needs its own out-of-sample test, and for SPX/Russell 2000 specifically,
the honest answer to "what's a profitable strategy" is still buy-and-hold,
by a wide margin, over this decade-plus window.

## ICT setup on SPX: liquidity sweep -> delivery -> inverse FVG (9+ pts) -> liquidity target

`python -m trading_bot.ict_ifvg_cli` (logic in `trading_bot/strategies/ict_ifvg.py`, 8 unit tests in
`tests/test_ict_ifvg.py`). The request named the concepts, not the rules, so the definitions below are this
repo's explicit interpretation - change them in the module docstring/`IctParams`, not by eye.

**Rules (all evaluated bar-by-bar, no lookahead; shorts are the exact price-mirror of longs):**
1. *Liquidity pool*: previous-session high/low, plus unswept fractal swing highs/lows (5 bars each side,
   usable only once confirmed).
2. *Sweep*: a bar trades through a sell-side pool (for a long).
3. *Inverse FVG*: a bearish 3-bar gap of **>= 9 index points** that formed in the leg into the sweep low is
   closed through by a bar close above its top (first time only).
4. *Delivery*: that bar is a displacement bar (body >= 50% of range, range >= mean of prior 20 bars) and
   closes back above the swept pool.
5. Enter next bar's open. Stop just beyond the inverted gap's far edge. Target: nearest unswept opposing
   pool at least 1R away (previous-day extreme / session extreme / swing). Flat at the session close.
   Max 2 trades/day, one at a time, 9:50-15:00 ET entries, 0.5 pt round-trip cost, stop assumed hit
   before target when both are inside one bar.

**Data**: 495 regular-session days, 2024-10-07 -> 2026-09-28, 10-minute SPX index bars from
`get_index_historicals` (`data_cache_ict/SPX_10m.csv`). Interpolated filler bars were dropped. Checked
against the independent `SPX_daily.csv`: 494/495 sessions matched (high std 0.18 pt, close std 1.6 pt).
Two data traps found on the way: the 10-minute endpoint returns *all-interpolated* (fake) bars for
2026-03-30 -> 2026-07-01 while 5-minute is real, so that window was rebuilt from 5-minute bars; and the
bar-count cap (~1500 bars/call) forces 10-day windows.

**Result (primary spec, fixed before looking at P&L except the stop change below):**

| | n | win | avg R | total pts | PF | max DD |
|---|---|---|---|---|---|
| All | 37 | 54% | +0.18 | +160 | 1.60 | 77 pts |
| Long | 19 | 47% | -0.02 | +22 | 1.14 | |
| Short | 18 | 61% | +0.39 | +138 | 2.25 | |

**Why this is not evidence of an edge:**
- 37 trades in two years. Bootstrap 95% CI on mean R is **[-0.17, +0.51]**.
- Random-entry control (same side / stop / target distance, random timing, 2000 draws): mean R -0.02;
  the real +0.18 beats 89.5% of draws, **p ~ 0.10** - suggestive, not significant, and this is one of
  ~25 configurations looked at.
- **Concentrated**: the top 3 trades (+55, +33, +31 pts) are 75% of the profit. Without them: +40 pts; without
  the top 5: -18 pts.
- **Stop-definition dependent**: with the stop beyond the *sweep* extreme instead (the other natural reading),
  27 trades, avg R -0.05, -37 pts. The gap-edge stop was adopted after the sweep stop produced only 3-4
  trades under a 30-pt risk cap (risk is typically 25-100 pts there) - a choice made on trade count, but both
  variants had been seen when it was made.
- **Long side has no edge** (-0.02 R); everything comes from shorts, which in a market that rose ~35% over the
  window is more likely a sample quirk than a structural feature.
- Target: only 30% of trades reach the liquidity target, 35% stop out, 35% end flat at the close. Fixed 1R/2R/3R
  targets give similar avg R (+0.21/+0.16/+0.17), so "liquidity targeting" adds nothing measurable.
- Larger minimum gap looked monotonically better (avg R +0.04 at 3 pts, 0.00 at 5, +0.13 at 7, +0.18 at 9,
  +0.36 at 15 with n=11), the one pattern that agrees with the ICT premise - but also shrinking samples.
- Cost: avg R falls to +0.10 at 2 pts round trip. SPX is not directly tradable; ES/MES fills, and
  gaps through stops, are not modelled beyond a fixed cost.

### 5-minute rerun (same rules; bar-count windows doubled to keep the same clock time)

`python -m trading_bot.ict_ifvg_cli --data data_cache_ict/SPX_5m.csv --bar-minutes 5` on 494 sessions
(2024-10-07 -> 2026-09-25, `SPX_5m.csv`; 5-minute bars had to be pulled in 4.5-day windows, ~100 calls).
Swing length / sweep window / lookbacks are scaled x2 so the pools and windows cover the same time as at 10m; that
scaling was fixed before looking at 5m results. Data check vs the daily file: high/low error std 0.15/0.20 pt.

| | n | win | avg R | total pts | PF |
|---|---|---|---|---|---|
| 5m all | 33 | 48% | +0.13 | +177 | 1.66 |
| 5m long / short | 16 / 17 | 62% / 35% | +0.30 / -0.03 | +119 / +58 | |
| 10m all (above) | 37 | 54% | +0.18 | +160 | 1.60 |
| 10m long / short | 19 / 18 | 47% / 61% | -0.02 / +0.39 | +22 / +138 | |

- **Not confirmed, and the long/short split flipped.** At 10m the edge was all shorts, at 5m it is all longs. On the
  same market and period, an edge that changes side with the bar size is noise, not a feature of the setup.
- 5m bootstrap 95% CI on mean R: **[-0.30, +0.59]**; random-entry control p ~ **0.22** (10m: 0.10).
- **Worse concentration**: the top 3 trades are +188 pts against a +177 total, so the other 30 net **-11 pts**
  (mean R without them -0.13). Year 1 (Oct24-Sep25) +0.51 R (n=14); Year 2 (Oct25-Sep26) **-0.14 R** (n=19).
- Stop beyond the sweep extreme now gives +0.07 R (27 trades) instead of -0.05: same sign-flip fragility.
- The one pattern that reproduced: bigger minimum gap = better. 5m avg R by min gap: 3: +0.10, 5: +0.20, 7: +0.15,
  9: +0.13, 12: +0.58 (n=17), 15: +0.90 (n=13, 77% win). Same direction as 10m (+0.36, n=11 at 15 pts).
  But these are the same market days (31 vs 36 trade-days, 15 shared), so this is one observation seen twice,
  not two independent confirmations; the 12/15-pt cut-offs are picked after the fact; and n=13-17.
  The 9-pt spec you asked for sits in the weakest part of that curve.

Not tested: 1-minute execution (a 9-pt gap is a bigger structure on 10m/5m than on 1m), pre-market/overnight liquidity (RTH data only), and any
out-of-sample period beyond the two years above.

## Forward paper trading: ICT SPX setup (5m), signal alerts, no orders

`trading_bot/paper_trading/ict_engine.py` + `python -m trading_bot.ict_paper_cli` (state:
`paper_trading_state/ict_spx_5m.json`, bootstrapped 2026-09-29 23:42Z; nothing before that is counted).
Places **no orders**. Two frozen variants run side by side (2026-09-30: only `gap15` alerts the user, `state['notify']=['gap15']`; `spec9` is tracked silently for comparison): `spec9` (the 9-pt gap asked for) and `gap15`
(the 15-pt cut-off - exploratory, chosen after seeing backtest results, so only fresh forward trades can
validate it). Each run replays the exact backtest detector on the last ~4 days of 5m bars and reports each new
signal and each paper exit exactly once (stable event ids). Checked: hourly rolling replays over
Apr-Jul 2025 (2,297 runs) reproduce the batch backtest trade-for-trade, no duplicate events
(`tests/test_ict_paper.py`).

Scheduled as a routine, weekdays at :03 past each UTC hour 14-21 (covers EDT and EST sessions). The routine
fetches the bars through Robinhood `get_index_historicals` (only reachable from an agent session), runs the CLI,
pushes one notification per `NOTIFY` line and commits the state on events / at the last run of the day.
**Robinhood alerts**: Robinhood cannot send free-text messages and cannot alert on the SPX index, so on each
signal the routine also creates two SPY price alerts (stop and target; SPX level converted at the live SPY/SPX
ratio, ~0.0996 - not 1/10, which would be ~23 SPX points off) that push through the Robinhood app, and pauses
them when the paper trade exits. Guardrails: SPY only, price_above/price_below only, max 6 active routine
alerts, never deletes, never touches your other alerts. Ledger: `paper_trading_state/ict_spx_robinhood_alerts.json`
(`trading_bot/ict_alerts_cli.py`, `tests/test_ict_alerts.py`). These alerts tell you when a paper trade *would*
have exited; the signal itself still arrives via the session push notification.

**Limits**: the scheduler's minimum interval is 1 hour, so an alert can be up to ~1h after the signal bar (paper
fills are simulated from bar data and are unaffected; a human could not have acted on a 1h-old 5m signal);
the routine only runs while the hosting session/environment is reachable; SPX is an index - there is no direct
execution, and the evidence for the setup is weak (see above), so the graduation bar is >= 30 closed forward
trades before anyone considers money, and execution safety (sizing, loss caps, kill switch) does not exist.

## Usage

```
pip install -r requirements.txt
python -m trading_bot.cli --symbols BTCUSD ETHUSD --interval 1d --start 2020-01-01
python -m trading_bot.walk_forward_cli --symbols BTCUSD ETHUSD --start 2020-01-01
```

`cli.py` outputs to `reports_out/`: a comparison CSV of metrics per strategy, a
log-scale equity-curve PNG, and a per-strategy trade log CSV. `walk_forward_cli.py`
outputs to `reports_out_wf/`: the same comparison CSV/PNG shape, plus a
`{symbol}_{family}_segments.csv` per strategy family showing which parameters were
selected each quarter and their in-sample score.

## Backtest methodology and its limits

- **No lookahead**: a strategy's signal at bar *t* is computed only from data
  through bar *t*, and only takes effect starting bar *t+1*
  (`position = signal.shift(1)`).
- **Fill assumption**: both the return calculation and the trade log price a fill
  at the *previous* bar's close. This is a standard, but optimistic, research
  simplification — it ignores intrabar price movement. `--slippage-bps` exists
  specifically to claw back some of that optimism; it is not a real order-book
  slippage model.
- **Costs**: `--fee-bps` and `--slippage-bps` (basis points of notional) are
  charged on every position change, both entering and exiting. Defaults (5 bps
  fee, 10 bps slippage) are a guess, not Robinhood's actual crypto cost structure
  — Robinhood prices crypto trades into the bid/ask spread rather than a published
  flat commission, so treat these numbers as adjustable assumptions to
  stress-test, not fact.
- **What this does NOT model**: partial fills, order rejects, exchange downtime,
  or the fact that a real position-sizing decision (e.g. all-in on every signal,
  as this engine does) is itself a risk choice most live traders wouldn't make.

A backtest that looks good under these assumptions is a reason to dig further
(different periods, walk-forward validation, transaction cost sensitivity) — not
a reason to wire up live execution.

## Layout

```
trading_bot/
  data/fetch.py               historical crypto OHLCV fetch + local CSV cache, gap-checked
  strategies/                  one file per strategy, each documenting its failure mode
  backtest/engine.py            single fixed-parameter backtest (no-lookahead, cost accounting)
  backtest/walk_forward.py      rolling re-optimize-then-test-out-of-sample validation
  backtest/bracket_engine.py     dip-buy + fixed take-profit/stop-loss/max-hold backtest
  backtest/metrics.py           CAGR, Sharpe, max drawdown, win rate, exposure
  options/black_scholes.py       dependency-free Black-Scholes pricer
  options/synthetic_bracket.py   real-underlying / modeled-premium options bracket backtest
  scanner/entry_exit.py          ATR-based entry/stop/target + select_new_candidates from one live scan pull
  paper_trading/engine.py        no-orders ETH paper trading, reuses walk_forward's own selection logic
  stock_paper_trading/engine.py  no-orders multi-position stock swing paper trading portfolio
  reports/summary.py            comparison table + equity curve chart
  cli.py                        crypto single-backtest entry point
  walk_forward_cli.py            crypto walk-forward entry point
  bracket_cli.py                 crypto dip-buy bracket entry point
  synthetic_options_cli.py        SPY/SPX synthetic options bracket + sensitivity sweep
  scanner_cli.py                  swing-scan entry/stop/target table from a saved scan JSON
  paper_trading_cli.py            advance (or bootstrap) one day of ETH paper trading against real data
tests/                          unit tests for every module above, incl. Black-Scholes correctness
data_cache_options/              real underlying/option data fetched during the SPY options work
  premiums/                       raw per-contract premium bars fetched (documented as unusable --
                                   kept for reference, not read by any code)
paper_trading_state/             persisted paper-trading JSON state, updated by each CLI run
data_cache_scanner/               saved live scan results + computed suggestion tables
```
