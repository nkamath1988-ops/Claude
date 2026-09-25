# BTC/ETH Strategy Backtester

Research-first automation for BTC/ETH: **this repo backtests trading strategies
against historical data. It does not place any live orders.** That's a deliberate
scope decision, not a placeholder — automating real-money trades before a strategy
has been validated is how accounts get blown up.

## Scope and what's deliberately NOT here

- **No live execution.** There is no code here that calls a broker/exchange to place
  an order. If/when a strategy earns that step, it's a separate, explicit addition —
  not something this repo does implicitly.
- **BTC/ETH only.** Forex and commodities were dropped from scope: no broker/data
  connector for either asset class is available in this environment.
- **Long-only, no leverage.** Matches what a spot crypto account can actually do;
  the engine has no concept of shorting or margin.

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
  data/fetch.py            historical OHLCV fetch + local CSV cache, gap-checked
  strategies/               one file per strategy, each documenting its failure mode
  backtest/engine.py         single fixed-parameter backtest (no-lookahead, cost accounting)
  backtest/walk_forward.py   rolling re-optimize-then-test-out-of-sample validation
  backtest/bracket_engine.py  dip-buy + fixed take-profit/stop-loss/max-hold backtest
  backtest/metrics.py        CAGR, Sharpe, max drawdown, win rate, exposure
  reports/summary.py         comparison table + equity curve chart
  cli.py                     single-backtest entry point
  walk_forward_cli.py         walk-forward entry point
  bracket_cli.py              dip-buy bracket entry point
tests/                       unit tests for engine/strategy/metric/walk-forward/bracket correctness
```
