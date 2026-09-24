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
strong secular crypto uptrend is a soft test for a trend-following benchmark; a
strategy comparison run over a different window (e.g. 2021-11 through 2022-11, the
prior bear market) could easily invert these rankings. Re-run with `--start`/`--end`
narrowed to specific regimes before concluding anything is robust.

## Usage

```
pip install -r requirements.txt
python -m trading_bot.cli --symbols BTCUSDT ETHUSDT --interval 1d --start 2020-01-01
```

Outputs to `reports_out/`: a comparison CSV of metrics per strategy, a log-scale
equity-curve PNG, and a per-strategy trade log CSV.

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
  data/fetch.py         historical OHLCV fetch + local CSV cache
  strategies/            one file per strategy, each documenting its failure mode
  backtest/engine.py      core backtest loop (no-lookahead, cost accounting)
  backtest/metrics.py     CAGR, Sharpe, max drawdown, win rate, exposure
  reports/summary.py      comparison table + equity curve chart
  cli.py                  entry point
tests/                    unit tests for engine/strategy/metric correctness
```
