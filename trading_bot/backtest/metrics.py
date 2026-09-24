import pandas as pd


def compute_metrics(equity: pd.Series, net_return: pd.Series, position: pd.Series,
                     trades: pd.DataFrame, periods_per_year: float) -> dict:
    if len(equity) < 2:
        return {}

    years = len(equity) / periods_per_year
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else float("nan")

    ann_vol = net_return.std() * (periods_per_year ** 0.5)
    ann_mean = net_return.mean() * periods_per_year
    sharpe = ann_mean / ann_vol if ann_vol > 0 else float("nan")

    drawdown = equity / equity.cummax() - 1
    max_drawdown = drawdown.min()

    n_trades = len(trades)
    win_rate = float((trades["pnl_pct"] > 0).mean()) if n_trades > 0 else float("nan")

    return {
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": ann_vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "num_trades": n_trades,
        "win_rate": win_rate,
        "exposure": float(position.mean()),
    }
