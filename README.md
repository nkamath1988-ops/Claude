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

## Data source: currently blocked, action needed

Historical OHLCV comes from Binance's public REST API (`api.binance.com`,
no key required) via `trading_bot/data/fetch.py`. **As of this writing, this
environment's network policy blocks outbound access to that host** (and to
`api.exchange.coinbase.com`, tried as an alternative) — confirmed via repeated
`connect_rejected` / HTTP 403 from the egress proxy.

To fix: open the environment's settings (title bar → environment selector →
**Edit** → **Network access**) and either switch to a broader access tier or add
`api.binance.com` to the allowed-domains list. Network policy changes on this
platform generally require a fresh session against the updated environment — they
don't take effect retroactively mid-session.

Until that's done, `fetch_klines()` will raise a connection error. The one bundled
data source this session *does* have (the Crypto.com MCP connector) only returns
the most recent 50 candles per call, which is not enough history for a trustworthy
backtest (50 daily bars = 50 days — not enough to see more than one market regime)
so it's intentionally not wired in as the primary source.

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
