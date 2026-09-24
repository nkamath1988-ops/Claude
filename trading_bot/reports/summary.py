from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestResult


def build_comparison_table(results: list[BacktestResult]) -> pd.DataFrame:
    rows = {r.strategy_name: r.metrics for r in results}
    table = pd.DataFrame(rows).T
    return table[[
        "total_return", "cagr", "annualized_volatility", "sharpe_ratio",
        "max_drawdown", "num_trades", "win_rate", "exposure",
    ]]


def plot_equity_curves(results: list[BacktestResult], out_path: str, title: str = "") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    for r in results:
        normalized = r.equity_curve / r.equity_curve.iloc[0]
        ax.plot(normalized.index, normalized.values, label=r.strategy_name)
    ax.set_yscale("log")
    ax.set_ylabel("Equity (normalized, log scale)")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
