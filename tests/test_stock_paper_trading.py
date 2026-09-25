import pytest

from trading_bot.stock_paper_trading.engine import (
    advance_day, close_due_positions, load_portfolio, new_portfolio,
    open_position, portfolio_equity, save_portfolio,
)


def test_open_position_deducts_allocated_capital():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10, max_concurrent=8)
    opened = open_position(p, "AAA", "2026-01-01", 100.0, 95.0, 110.0)
    assert opened is True
    assert p.cash == pytest.approx(9000.0)
    assert len(p.open_positions) == 1


def test_open_position_rejects_duplicate_symbol():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10, max_concurrent=8)
    open_position(p, "AAA", "2026-01-01", 100.0, 95.0, 110.0)
    opened_again = open_position(p, "AAA", "2026-01-02", 105.0, 100.0, 115.0)
    assert opened_again is False
    assert len(p.open_positions) == 1


def test_open_position_respects_max_concurrent():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10, max_concurrent=2)
    assert open_position(p, "AAA", "d", 100.0, 95.0, 110.0) is True
    assert open_position(p, "BBB", "d", 100.0, 95.0, 110.0) is True
    assert open_position(p, "CCC", "d", 100.0, 95.0, 110.0) is False
    assert len(p.open_positions) == 2


def test_open_position_rejects_when_insufficient_cash():
    p = new_portfolio(total_capital=1000, capital_per_trade_pct=0.60, max_concurrent=8)
    assert open_position(p, "AAA", "d", 100.0, 95.0, 110.0) is True  # uses 600
    assert open_position(p, "BBB", "d", 100.0, 95.0, 110.0) is False  # needs 600, only 400 left


def test_take_profit_closes_at_target_price():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10, cost_bps=0)
    open_position(p, "AAA", "2026-01-01", 100.0, 90.0, 110.0)
    close_due_positions(p, "2026-01-02", {"AAA": {"high": 111.0, "low": 99.0, "close": 108.0}})
    assert len(p.open_positions) == 0
    trade = p.closed_trades[0]
    assert trade["exit_reason"] == "take_profit"
    assert trade["exit_price"] == pytest.approx(110.0)
    assert trade["pnl_pct"] == pytest.approx(0.10)


def test_stop_loss_closes_at_stop_price():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10, cost_bps=0)
    open_position(p, "AAA", "2026-01-01", 100.0, 90.0, 110.0)
    close_due_positions(p, "2026-01-02", {"AAA": {"high": 101.0, "low": 89.0, "close": 92.0}})
    trade = p.closed_trades[0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["exit_price"] == pytest.approx(90.0)
    assert trade["pnl_pct"] == pytest.approx(-0.10)


def test_stop_wins_tiebreak_when_both_touched_same_day():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10, cost_bps=0)
    open_position(p, "AAA", "2026-01-01", 100.0, 90.0, 110.0)
    close_due_positions(p, "2026-01-02", {"AAA": {"high": 120.0, "low": 80.0, "close": 100.0}})
    assert p.closed_trades[0]["exit_reason"] == "stop_loss"


def test_max_holding_days_forces_exit_at_close():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10, max_holding_days=2, cost_bps=0)
    open_position(p, "AAA", "2026-01-01", 100.0, 90.0, 110.0)
    close_due_positions(p, "2026-01-02", {"AAA": {"high": 102.0, "low": 98.0, "close": 101.0}})
    assert len(p.open_positions) == 1  # day 1 of holding, not due yet
    close_due_positions(p, "2026-01-03", {"AAA": {"high": 103.0, "low": 99.0, "close": 102.0}})
    trade = p.closed_trades[0]
    assert trade["exit_reason"] == "max_holding_days"
    assert trade["exit_price"] == pytest.approx(102.0)


def test_missing_price_data_leaves_position_open():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10)
    open_position(p, "AAA", "2026-01-01", 100.0, 90.0, 110.0)
    close_due_positions(p, "2026-01-02", {})  # no data for AAA today
    assert len(p.open_positions) == 1
    assert p.open_positions[0]["days_held"] == 0  # not incremented on a data-gap day


def test_cost_charged_once_round_trip():
    fee_bps = 10.0
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10, cost_bps=fee_bps)
    open_position(p, "AAA", "2026-01-01", 100.0, 90.0, 110.0)
    close_due_positions(p, "2026-01-02", {"AAA": {"high": 111.0, "low": 99.0, "close": 108.0}})
    cost_rate = fee_bps / 10000.0
    expected_pnl = 0.10 - 2 * cost_rate
    assert p.closed_trades[0]["pnl_pct"] == pytest.approx(expected_pnl)


def test_advance_day_is_idempotent():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10)
    candidates = [{"symbol": "AAA", "entry_price": 100.0, "stop_price": 90.0, "target_price": 110.0}]
    advance_day(p, "2026-01-01", {}, candidates)
    n_open_after_first = len(p.open_positions)
    n_cash_after_first = p.cash
    advance_day(p, "2026-01-01", {}, candidates)  # same date again
    assert len(p.open_positions) == n_open_after_first
    assert p.cash == pytest.approx(n_cash_after_first)


def test_advance_day_processes_exits_before_new_entries_same_day():
    # at max_concurrent=1: an existing position closes today, freeing a slot a
    # new candidate should be able to fill on the SAME call.
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10, max_concurrent=1, cost_bps=0)
    open_position(p, "AAA", "2026-01-01", 100.0, 90.0, 110.0)
    new_candidates = [{"symbol": "BBB", "entry_price": 50.0, "stop_price": 45.0, "target_price": 55.0}]
    advance_day(p, "2026-01-02", {"AAA": {"high": 111.0, "low": 99.0, "close": 108.0}}, new_candidates)
    assert len(p.open_positions) == 1
    assert p.open_positions[0]["symbol"] == "BBB"


def test_portfolio_equity_marks_open_positions_to_market():
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10)
    open_position(p, "AAA", "2026-01-01", 100.0, 90.0, 110.0)
    equity_flat = portfolio_equity(p)  # no current price -> valued at allocation
    assert equity_flat == pytest.approx(10000.0)
    equity_up = portfolio_equity(p, {"AAA": 105.0})
    assert equity_up == pytest.approx(9000.0 + 1000.0 * 1.05)


def test_save_and_load_roundtrip(tmp_path):
    p = new_portfolio(total_capital=10000, capital_per_trade_pct=0.10)
    open_position(p, "AAA", "2026-01-01", 100.0, 90.0, 110.0)
    path = str(tmp_path / "portfolio.json")
    save_portfolio(p, path)
    loaded = load_portfolio(path)
    assert loaded.cash == pytest.approx(p.cash)
    assert loaded.open_positions == p.open_positions


def test_load_missing_portfolio_returns_none(tmp_path):
    assert load_portfolio(str(tmp_path / "nope.json")) is None
