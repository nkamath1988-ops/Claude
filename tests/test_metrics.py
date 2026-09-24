import numpy as np
import pandas as pd
import pytest

from trading_bot.backtest.metrics import compute_metrics


def test_metrics_on_known_synthetic_series():
    # equity doubles then halves back: total_return 0, but real drawdown along the way
    equity = pd.Series([100.0, 200.0, 50.0, 100.0])
    net_return = equity.pct_change().fillna(0)
    position = pd.Series([1, 1, 1, 1])
    trades = pd.DataFrame({"pnl_pct": [0.5, -0.3, 0.1]})

    m = compute_metrics(equity, net_return, position, trades, periods_per_year=365)

    assert m["total_return"] == pytest.approx(0.0, abs=1e-9)
    assert m["max_drawdown"] == pytest.approx(-0.75, rel=1e-9)  # 200 -> 50
    assert m["num_trades"] == 3
    assert m["win_rate"] == pytest.approx(2 / 3, rel=1e-9)
    assert m["exposure"] == pytest.approx(1.0)


def test_metrics_empty_trades_gives_nan_win_rate():
    equity = pd.Series([100.0, 101.0, 102.0])
    net_return = equity.pct_change().fillna(0)
    position = pd.Series([0, 0, 0])
    trades = pd.DataFrame(columns=["pnl_pct"])

    m = compute_metrics(equity, net_return, position, trades, periods_per_year=365)
    assert m["num_trades"] == 0
    assert np.isnan(m["win_rate"])
    assert m["exposure"] == 0.0
